# CTX-01 · 上下文超预算后的发送前压缩

- **关联需求**：[上下文预算与压缩方案](../../architecture/context-compaction-proposal.md)§1；既有CTX-C01候选的本次具体需求输入。
- **任务目标**：让已被预检判为需要压缩的普通长对话，在发送前完成现有压缩与重组，保留真实业务身份，不依赖调大额度或新增审核。
- **当前阶段**：首批代码与离线验收已交付；真实接入未测，父功能PARTIAL。
- **顺序**：排在已有[PUB-01](PUB-01_acceptance-publication.md)之后；这是用户指定的执行顺序，不是发布功能的技术依赖，不插队替换当前断点。
- **授权与停止点**：最新用户已授权按收敛方案实施Easel侧去重与官方压缩接入，并完成离线测试；直接使用easel-v2-rebuild，保留既有Dirty。不升级、不修改OpenClaw，不调大额度、不加审核，不部署、不付费、不恢复制作；本批代码、离线测试与文档收口后停止。
- **范围 / 不做**：自动注入去重，并在公共发送前复用官方sessions.describe/compact。不上新Agent/Gate/记忆服务、不提高额度；上一轮压力不能冒充当前实时预算，完整覆盖缺口见方案§1/§6。
- **基线与现场**：Easel长期分支easel-v2-rebuild，存在既有Dirty；分析依据为本轮真实日志及本机OpenClaw代码。开工时重新核对HEAD、源码来源、运行依赖和既有本机补丁；原视频制作保持停止。
- **完成条件**：方案§6；超预算、正常输入、压缩失败/无进展、取消恢复、提案/授权身份及UNKNOWN正反例均需具名证据。软件通过与真实诊断通过分别记录。
- **相关设计与文件**：方案§3；easel/conversation_bridge.py、easel/conversation_pipeline.py的turn_context、OpenClaw上下文运行时及最终请求观察点。外部源码交付边界须先核实。

## 实施顺序

唯一任务拆分维护在[当前方案§5](../../architecture/context-compaction-proposal.md#5-实施任务与状态)：官方接口离线验证→输入投影去重→公共发送前准备→关联回归→另行授权后的真实定向验证。原“修改OpenClaw恢复路径”拆分不再执行。

## 执行记录与结果

2026-10-23：用户批准将此需求登记在PUB-01之后。已形成方案及任务拆分，未修改代码/配置、未调用模型诊断、未恢复视频。文档登记完成；软件实现、部署及真实验证均NOT_TESTED。

**未闭合风险**：官方describe是上一轮预算，无当前待发请求精确预检；compact没有调用方幂等键/expectedSessionId；断连须读回，不能盲重试。重复注入体积占比和真实摘要待验证；身份/并发已有首批离线证据，真实Gateway集成仍未测。原length唯一因果仍未证实。

**唯一下一动作**：本轮在代码、离线验收与文档收口后停止。后续需另行授权部署及官方长会话定向验证；原视频不恢复，原完整实时前置目标保留未闭合，不以首批能力代替父任务完成。

## 2026-10-23授权及路线调整

用户先授权在唯一主线easel-v2-rebuild完成代码与离线测试，保留Dirty，不部署、不恢复制作；随后明确“不要修改OpenClaw”，询问通过更新解决。最新边界优先：停止自定义网关补丁，先只读评估官方升级，不执行安装、重启或配置迁移。此前调查未修改OpenClaw安装目录或业务代码。

当前安装包2026.9.4；npm查询latest为2026.10.6、extended-stable为2026.9.33、beta为2026.10.10-beta.3。版本为本次查询事实，不代表新版已经修复本问题。需核对发布说明及新版预检/恢复实现、Easel插件兼容和本机已有补丁，再形成具名升级与回退操作；实际升级属于部署变更，待明确授权。原length唯一因果仍未证实。


## 2026-10-23 · 官方2026.10.6升级核查

### 结论与证据

**不建议将直接升级作为CTX-01修复。** 新版仍把普通历史压力估算视为诊断；未覆盖本任务要求的“普通compact_only必先压缩”。这是与我们需求的行为差异，不能仅凭该日志称为官方缺陷，也不能保证升级后原length消失。原供应商唯一因果仍未证实。

- Easel核查基线：easel-v2-rebuild / 08bb6979，既有Dirty保留。只读下载官方2026.9.4、2026.10.6发布包至临时目录，按包元数据SHA-512核验成功，未安装或执行包生命周期。新版包校验值：`sha512-jSpQPa2Jw5rG0J2GC07j9+qHtVYIuoHjgccU88JeS+p7188sBCnvIJeuaiNPHj1zsWkuHcBv443QiEUh7qrxwA==`。
- [新版预检源码](https://github.com/openclaw/openclaw/blob/v2026.10.6/src/agents/embedded-agent-runner/run/attempt-prompt-preflight.ts)：prepareEmbeddedAttemptPromptPreflight仍仅在compactionReplay压力或新增pendingInputTokens达到整个contextTokenBudget时短路。普通route非fits仍记录admitted provider attempt。发布包dist/builtin-openclaw-CcrkVuBH.mjs同样如此。
- [官方测试](https://github.com/openclaw/openclaw/blob/v2026.10.6/src/agents/embedded-agent-runner/run/attempt-prompt-preflight.test.ts)：heuristic pressure用例明确要求shouldCompact=true且skipPromptSubmission=false、preflightRecovery缺失。不是仅依据发布说明推断。
- [输入预算源码](https://github.com/openclaw/openclaw/blob/v2026.10.6/src/agents/sessions/compaction/request-budget.ts)：新增pendingTokens只包括当前待送用户/图片与额外上下文；fixedTokens另列，不包括完整历史。因此不能拿它替代本次281483总估算超过236000预算的历史压力条件。
- 新版原生会话仍可在prompt前通过checkCompaction根据上一助手回执/上下文用量触发原有压缩，也改进了压缩请求预算；这与普通启发式预检路由不同。原故障缺少完整最终请求和有效usage，未做相同真实会话重放，不能断言新版在所有路径上都不会压缩。

### 离线证据

对两版发布包提取的原始预检函数，在临时VM中注入合成压力与无副作用依赖：6个断言PASS。普通compact_only两版均不短路；compactionReplay两版均进入恢复；pending输入达到整个窗口仅新版进入恢复。输入使用281483/236000压力数值与合成正文，没有个人内容。测试脚本仅在临时目录，按上述三个分支可复现；这是分支验证，**不是完整Gateway集成或真实模型测试**。初始探针曾因函数定位及缺少mock依赖失败，完善测试夹具后重跑通过，未改被测函数。

### Easel兼容性

| 核对项 | 结果与影响 |
|---|---|
| 插件公开入口 | 新版仍导出plugin-sdk/plugin-entry及definePluginEntry；registerTool/registerHttpRoute、before_prompt_build、before_agent_run、before_tool_call、agent_end及诊断hooks仍存在。toolsAllow合并和block语义仍有实现。只证明静态接口存在，不证明加载/时序PASS。 |
| 插件版本声明 | `agents/plugins/easel-work/package.json` 仍限定2026.9.x；2026.10.6超出声明。需要通过新版集成验证后再调整Easel声明，不能先放宽范围假称兼容。 |
| 对话HTTP | /v1/chat/completions及x-openclaw-session-key仍存在。新版有会话覆盖授权检查；原生sessionId/runId绑定、工具票据、自动回传和UNKNOWN保护需回归。 |
| 本机修改 | 将官方旧包10616个非node_modules文件与安装目录比较，发现5个文件内容不同：fetch-guard、provider-transport-fetch、principal、builtin-openclaw、src协议schema；另有本机easel-structured-result模块。旧包生命周期标记缺失不作为代码修改。此比较不覆盖整个嵌套依赖树。 |
| 修改影响 | 涉及easelStructuredResult字段/受控工具、请求结果观察和传输、length不进入settled-tool续接。新版没有该自定义协议字段，直接覆盖会移除改动；不照搬补丁。当前Easel生产配置源码使用direct-api，检索主源码未发现旧自定义字段调用，不能据残留补丁就宣称当前规划一定失效；应确认实际部署调用者及length/工具续接等价行为。 |
| 运行兼容 | 尚未在受支持Node启动新版Gateway，未连接生产配置/数据库；启动、状态迁移、插件加载与端到端兼容均NOT_TESTED。 |

### Node与回退方案（未执行）

[官方发布说明](https://github.com/openclaw/openclaw/releases/tag/v2026.10.6)与包engines一致：`>=24.22.1 <25 || >=26.12.1`。Shell实测v24.21.0；运行中Gateway的可执行文件也是该24.21.0安装目录的node。建议未来选择受支持的24.x修订版，减少跨主版本变化；本轮未安装。仅改shell PATH不够，Easel命令解析优先邻近node，Gateway服务/启动脚本的真实路径必须一并验证。

将来获准升级时：

1. 先在独立临时状态、受支持Node和假模型上验证原生插件、权限/身份、length/tool-call终止与压缩正反例，不接入生产凭证。现有桥接和流式测试可复用；不得将Hash导出变更造成的测试加载失败当成业务故障。
2. 切换前确认无在途并暂停相关写入者；保留旧Node、完整旧安装（含既有补丁）、启动入口/服务定义和环境引用。同一时间点私下备份实际profile配置及include、会话/共享及各Agent数据库、凭证与工作区。SQLite使用一致性备份或停写后成套保存，不能只复制活跃主db而遗漏WAL。Easel业务库及身份关联同步留恢复点，个人数据不入Git。
3. 固定目标2026.10.6与Node版本，先预检再按官方受支持流程切换；当前2026.9.4的旧更新器不自动获得新版恢复能力。不得直接全局覆盖后假设可退，不运行生产模型或恢复作品来验收安装。
4. 未迁移且无新状态写入时，失败可恢复原安装/入口及同代配置；一旦发生状态迁移或新写入，不能仅降级npm包。保持写入停止，先保存失败现场，再恢复**同代完整状态备份+匹配旧运行时**，不得修改schema/version标记绕过拒绝。回退会丢失备份后新增状态，需明确影响；当前停止制作有助于缩小窗口。
5. 回退后验证运行版本、服务健康、插件、原会话/提案/UNKNOWN及停止断点；不清理旧包/备份直至验收。24.21.0只作为短期应急恢复点，不能把它当成新版支持的Node。

依据：[官方回退指南](https://docs.openclaw.ai/install/updating/rollback-and-recovery)。备份与回退均为方案，**未实际创建生产恢复点或演练回退**。

### 本轮收口

只读代码核查和6项函数分支检查完成；兼容性PARTIAL，完整SOFTWARE_PASS/DEPLOY_PASS/REAL_PRODUCTION_PASS均NOT_TESTED。本轮只更新CTX方案及入口文档，无产品代码、OpenClaw代码、配置或生产状态写入；未安装升级、重启、付费、制作或提交推送。保留原视频停止断点。升级不能单独满足CTX-01，父任务保持PARTIAL，不以依赖研究结束冒充修复完成。


## 2026-10-23 · Easel侧方案收敛（实施前）

用户明确不升级、不修改OpenClaw，要求先收敛方案，不调大额度、不增加限制、不改代码、不恢复制作。分支/HEAD保持easel-v2-rebuild/08bb6979，既有Dirty和个人资料保留。分类为已授权CTX-01设计工作，处理本次已证实上下文压力问题；原视频停止断点不动。

核对当前2026.9.4官方源码确认：sessions.describe可投影有效contextBudgetStatus；sessions.compact不带maxLines可复用原生摘要，带maxLines是历史截断。官方互斥会拒绝active/queued，因此在Easel发送前接线，不从Agent运行中调用。两种RPC均未向生产执行。

Easel源码确认reserve经turn_context保留历史sources全文，当前原话又在prompt末尾附加；建议只改自动注入投影，完整来源仍由现有工具读取。用户、handoff和task_result统一经VideoChat._deliver准备，不另造调度器；已有设备签名RPC可复用，但需修正目标Gateway绑定和错误/超时分类后才能用于会话维护。

[当前方案](../../architecture/context-compaction-proposal.md)已重写为Easel侧首批：去重+有效历史压力触发官方压缩+原回合恢复。旧升级记录留作依据，Node升级/回退不再是本期前置。没有公开当前请求dry-run预算接口的证据，首次输入暴增和回合内增长不能宣称覆盖；这一首批切片仍待评审，原目标未被降低或标完成。

本轮仅源码/官方文档调查及仓库文档一致性检查；未新增产品代码或运行功能测试。SOFTWARE_PASS/DEPLOY_PASS/REAL_PRODUCTION_PASS均NOT_TESTED；此前6项预检函数探针只是上轮证据。未提交推送，未执行任何压缩、付费或制作。本轮按仅方案授权收口。

## 首批实施授权

用户明确按收敛方案实施CTX-01.1～.4，在easel-v2-rebuild保留已有改动；不升级或修改OpenClaw，不调大额度、不加审核，暂不部署、不恢复制作。本轮停止点为首批代码、适用离线测试与文档收口；真实调用/部署仍NOT_TESTED，不自动提交推送长期主线。接受首批只使用有效历史压力、不能保证首次暴增输入实时预检的既定边界。


## 首批实施结果与离线验收

本批分类为用户明确授权的CTX-01当前故障修复（CURRENT_BLOCKER），依据为已有超预算未压缩证据；只完成方案.1～.4，原视频停止断点保持不变。受测版本为easel-v2-rebuild / 08bb6979加本批工作区增量，未提交、推送或部署。

### 实现范围

- `conversation_pipeline.turn_context`只将自动注入的历史sources正文改成引用；本轮原话保留一次，完整来源仍由`easel_work_context`读取。Profile/Director、提案、权限、费用和UNKNOWN沿用现有权威状态。
- `conversation_compaction.ContextPreparation`通过现有设备签名WS客户端连接与VideoChat相同的Gateway，调用公开`sessions.describe / sessions.compact`，不传maxLines。无有效压力不调用摘要；有效历史压力先压缩，再重建prompt/hash、提案可见范围及当前版本，沿同一待发回合发送。
- 用户、handoff和task_result复用`VideoChat._deliver`；结果事件完整保留。使用既有payload、交付租约和结果回传tick记录与恢复，不加表、审核、调度器或tokenizer。
- 超时/pending先持久记为压缩结果未定，恢复只读回，不重复付费压缩。新检查点必须同时满足原身份/模型/窗口、压力清除及无活动运行；仅检查点增加不能放行。明确失败保留未发送消息，可由既有停止回答释放；不把准备失败记为已执行的原生UNKNOWN。提交聊天后仍走原UNKNOWN保护，不自动重发。
- 压缩中取消/撤销不发送聊天；取消不会回滚可能已完成的官方摘要。官方明确拒绝与方法缺失分开；真实socket超时按RPC设置，凭证与原始响应不入诊断。

### 验证证据

- Python关联回归：`.venv/bin/python -m pytest -q tests/production/test_context_preparation.py tests/production/test_conversation*.py tests/test_gateway_endpoint.py tests/test_chat_question_replay.py`：**252 passed，1 failed**。含CTX新增32项；新用例覆盖去重和完整来源、有效/无效压力、同Gateway握手与参数、失败/no-op/无进展、并发、取消/撤销、断连读回、用户/交接/结果三入口及一次发送。
- 唯一失败为既有`test_blocker_does_not_offer_input_mutation_during_active_run`：测试要求音乐缺口无choices，开工前Dirty已返回合法resume选项。已用开工前备份源码在测试进程内重跑，得到相同断言失败；未回退磁盘代码、未改BGM逻辑、未删除断言或skip。本批不声称整组全绿。
- 原生插件关联回归：`node --test tests/production/workBridgePlugin.test.mjs tests/production/mainPipelinePlugin.test.mjs tests/production/executionWaitPlugin.test.mjs`：**33 passed**。既有提案、原生身份、工具票据、等待/UNKNOWN与交接保护继续生效。
- 文档路径检查：`scripts/validate_document_paths.py`验证2984条引用、572个文档/提示文件，PASS；`git diff --check` PASS。对开工前Dirty备份逐文件校验，本任务范围外已有改动保持原样。
- 三个既有HTTP模拟用例补入无压力RPC夹具，避免新增发送前描述步骤误连外部；不放宽业务断言。测试使用合成会话、临时业务库和假Gateway，不调用真实摘要/模型或生产操作。

**验收状态**：CTX首批新增离线范围SOFTWARE_PASS；关联回归PARTIAL（上述既有失败）。DEPLOY_PASS、真实官方压缩及后续请求验证、REAL_PRODUCTION_PASS、CREATOR_ACCEPTED均NOT_TESTED。未升级或修改OpenClaw、未调额度、未新增审核、未恢复制作。

**未验证与后续**：已安装Gateway的实际设备授权、运行时同会话竞争与真实摘要效果仍待.5；首次突然增大的输入、回合内增长和原length唯一因果不在本批已证明范围。官方接口没有expectedSessionId或请求幂等键，外部客户端同key重建的竞争边界仍保留。部署及定向验证需另获授权，不自行恢复原片。


### 授权部署与Web复验（第03轮进行中）

用户后续明确授权部署及定向模型调用，并要求通过Web创作新片；已进一步确认本片具体付费制作范围。源码为easel-v2-rebuild / 08bb6979及保留的Dirty，前端构建PASS，已通过正式LaunchAgent部署。首轮手工启动未继承生产开关造成入口失败，已恢复正式启动定义并回原Web定向复验，首次失败保留。未修改或升级OpenClaw。用户与handoff真实回合已通过官方describe及无压力准备路径，context_preparation=ready、chat_submitted=true；压力触发官方compact及压缩后继续仍NOT_TESTED，不用普通新片替代压力样本。运行证据与唯一断点见[第03轮](runs/2026-10-23-web-e2e-03.md)，父任务维持PARTIAL。

### 第03轮当前阻断：剪辑抽帧参数纠正（2026-10-24）

真实供给和配音成功后，剪辑模型请求12.8秒（源总长12.8）及19.4秒（源总长19.386033）的画面；抽帧合法上界为实际末帧时间，前者已超末帧、后者亦超源长。工具ValueError被统一转换为invalid_model_output并立即退出，没有将可纠正的参数边界返回模型。终态失败已自动回到原Web；不等于成片回传通过。

修复范围：保留真实抽帧边界，只将确定的抽帧时间越界作为结构化参数错误，携带实际上界返回同一工具交换，使用已有格式纠正/轮次预算；不增加预算、审核或自动生产重试，不吞掉未知工具、越权、重复调用及运行故障。补充工具说明避免把总长当末帧；覆盖越界纠正、同批多个越界、预算耗尽、范围保护和真实FFmpeg边界。测试部署后经原Web合法恢复剪辑，复用本片新素材与配音；不重跑供给、不发布。

定向软件验证：model_tasks、抽帧边界、静态图、首剪供给31项PASS；revision_pipeline、visual_repair、audio_technical_evidence12项PASS。一次命令包含不存在的测试路径，零收集已纠正，未计通过。真实本片两个视频离线回放均准确拒绝原时点，按返回上界成功解码；无模型调用。文档2987引用检查与diff检查PASS。已按本轮部署授权重启正式LaunchAgent，从原Web请求合法恢复提案，未重跑供给。

第一次修复后恢复遇command_conflict，未发起新MODEL：额外工具说明改变原请求hash，现有操作幂等保护正确拒绝。撤回说明修改，核对工具定义与保存请求逐字段一致，只保留执行时纠正反馈；43项关联用例再次PASS并部署。未更换操作标识、未放宽去重、未SQL改状态。原Web请求既有resume提案，等待实际受理。

真实CTX压力样本（2026-10-24）：恢复请求触发官方历史压力估算245027 > 236000预留后预算（窗口256000），Easel自动调用官方compact并得到新checkpoint；压缩回执tokens_before=186751、tokens_after=30390（与估算不同口径，不混算降幅），原回合chat_submitted=true。原Web随后正常返回服务端受理的恢复提案，未重复用户消息、未调大额度或改OpenClaw。此具名样本的压力触发→官方压缩→原请求完成PASS，首次突增和所有模型泛化仍不作保证。私有身份及回执保存在本机诊断目录real-compaction.json。

### 第03轮第二处实现阻断：未改原声镜头被视觉修订误拒

首版渲染和技术检查成功，已有视觉抽样检查触发局部修订。最后模型回执已修正前两次引用/观察区间错误，但assert_visual_repair对任意source_audio镜头一律拒绝，实际保存回执中的AudioClip及带原声s4镜头完全未改，属于程序误拒。修复为比较完整AudioClip、每个原声镜头完整字段与实际时间线位置：原声镜头保持原样时允许修改其他无声镜头；新增/删除/改变原声镜头、增益、源起点、淡出或时间位置仍拒绝。不放宽声音合同、不新增审核。25项关联测试PASS，包含新增正反例；本片最终修订回执离线作用域校验PASS。随后部署并从原Web恢复现有修订，不重跑素材/配音。

第03轮最终断点：第二处修复后原Web恢复成功，保存的修订回执通过，未重新生成配音或检索，产出revision 2并自动回传、浏览器完整播放30秒。当前预览仍有视觉检查失败，声音及完整语义未测；没有在途调用，历史UNKNOWN六项不变。CTX真实压缩样本PASS；视频质量和PUB剩余项不混记CTX通过，亦不声称整组父目标闭环。停止追加制作/付费，等待Creator审片。


## 2026-10-24 · 官方中途压缩后的同回合衔接修复

用户授权Easel侧修复、离线测试后部署，不改/升级OpenClaw，不恢复制作，真实原场景由用户验证。归因来自同轮日志及已安装原生生命周期源码：一次内部尝试因context overflow触发agent_end，随后官方压缩成功并使用continuation prompt重试；Easel曾在第一次agent_end清除prepared并end持久回合，后续claim/门禁拒绝。不能仅移除prompt检查，否则会放宽首次绑定。

复用原claim：只对已经绑定的同一原生sessionKey/sessionId/runId，在原生错误回执明确为上下文溢出时保留回合准备信息、清掉过期工具ticket，不发送最终end。续跑仍向原claim提交最初已鉴权prompt，并核对服务端回合仍active；新continuation prompt仅用于本次before_agent_run匹配，不覆盖用户原话或生成授权。正常终态/其他错误仍end。跨run/session、已结束、撤销或服务不可用均不放行，不增加自动重发或模型调用，不提高额度。

离线测试覆盖官方事件顺序、continuation prompt变化、旧ticket清理、终态只关闭一次、通用工具仍被拒绝、跨run隔离、服务端撤销、非overflow错误、用户正文中的overflow不被当成原生错误；Python验证同回合可再次claim，改prompt/换run/结束后均拒绝。当前真实业务没有重放，压缩后原对话实际继续NOT_TESTED；父任务仍PARTIAL。


本轮离线与部署收口：全量后端2410 passed / 16 skipped / 14原警告（后续增加1个claim正反例，并补齐旧revision提案读取和空changes_json处理）；最终关联175 passed，前端与插件183 passed。文档路径检查与git diff --check通过。已重启本机Easel服务及网关加载仓库内easel-work插件，/api/status返回gateway=true；不升级/修改OpenClaw源码或配置，无新增模型/媒体调用。部署前后10类业务表摘要完全一致，原未确认方案及所有生产断点保留。私有摘要证据位于outputs/_diagnostics/2026-10-24-plan-revision-compaction/，不纳入Git。SOFTWARE_PASS；真实原对话修订与压缩续跑NOT_TESTED，由用户自行验证。本轮后续授权：仅提交并推送本修复代码、测试与文档到easel-v2-rebuild，排除个人及运行文件；不恢复制作。


## CRE-01主线多轮调试衔接（2026-10-25）

沿原CRE-01授权在主工作区V2修复，不另建CTX任务或更换OpenClaw：结果等待载荷复用既有任务视图，原Task请求不改；新增仅已结束、同模型、空length回复后下一条新消息的受控官方压缩触发，保留压缩未知不重发及旧消息不重派。真实诊断官方压缩220494→58918 Token后同会话只读取回方案，自动触发条件的正反例另据离线证据，不混为真实自动触发。首次暴增输入实时预算预估仍未覆盖。完整变更、验收和运行身份唯一见[CRE-01本轮记录](runs/2026-10-25-web-e2e-02.md)。
