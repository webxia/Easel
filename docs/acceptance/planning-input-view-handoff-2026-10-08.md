# 稳定自主出片 Goal：Planning @9 交接

**2026-10-09 最新运行状态：已按用户要求本地提交并重启服务。** 代码commit82b66519、source90ab1935/223文件；Web7860 PID22399、专用Gateway18789 PID22325均健康，Runtime2026.9.4未更换。日志精确归档，当前无活动Job/模型任务，旧Creation与UNKNOWN/预算不变。103个选定文件提交，1190个批量历史输出原样保留未提交；未push/发布或发起真实评测。此前168PASS+原生1PASS按源摘要复用，前端构建另通过。[运行记录](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-commit-restart-2026-10-09.json)。

**2026-10-09 最新收尾：三项机械约束简化已实现并验证。** 已核断线撤回未改变六文件partial状态，保留并补齐下游；intake6查询0～3条、visual-requirements2按完整唯一ID对齐、空字符串偏好备注；保留原回复、规范化摘要、旧intake5/visual1和冷恢复，缺项/错帧/真实不符/授权等边界不变。当前source `90ab1935538ab3044c61ae1889392cfc42ae39ebfd26d3a78dc03ea1b1fb0272`/223文件，最终相关168PASS（Job `wc_job_rau70u9oykDBj0vX`）+原生1PASS/5本地替身HTTP（Job `wc_job_ktVJZcoiSk3o457P`），全部已取终态。302保护/142fixture/5封存账本及源码/测试围栏一致，独立Reviewer未取得，无新真实模型、quota、媒体、Build或部署推送发布。[结果](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-advisory-validation-2026-10-09.json)，私有原`advisory-validation-20261009T090924Z`含最终证据。三项软件已完成，不再重做；真实上游UNKNOWN与旧父池停止仍保留，下一执行须先原请求对账，不自动分配新批。以下为历史说明。

**2026-10-09 最新用户决策：移除自动配额查询，盘点非必要校验。** 执行器已改本地check_authorized_route，无quota网络/25%门槛，保留原凭证/route/无fallback/本地预算与UNKNOWN；15+4定向测试PASS、无新真实请求。优先候选是query条数/语言硬门槛、同帧checks按ID规范排序和非必需preference_notes；这些仅盘点未实现，详情见原Task“移除自动配额查询与非必要校验盘点”。Planning/Material/Hypit生产源码保持e5cb1c59，旧失败、父池和UNKNOWN保持，不能重开旧manifest。私有证据remove-automatic-quota-20261009T082246Z；不再为续接主动查quota，后续原请求对账与业务准入仍独立。

**2026-10-09 当前断点：第一单元原生及第二单元软件已完成，新资格首例因上游UNKNOWN停止。** 当前source e5cb1c593e1d743e81c64c0c38f7144c2fac26b7f4712a7f3f34e101975d81aa/223文件；49当前组合PASS、当前原生1PASS/36.44s/5本地HTTP，旧67及首次原生1PASS作为各自范围证据。Material compact/Truth接stage-output-receipts@1政策/凭据，旧缓存与原请求保持，原数据安全保留，不改变合法拒绝/repair/queries规则。[软件收尾](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-output-consumers-2026-10-09.json)。新授权池`output-admission-continuation-80http-v1`首batch-01 manifest015cf7d6已冻结6载体，Job wc_job_fyWdm7hui8zUqGV3 exit2，首例FAIL/1HTTP/71.890s，原run easel-6d9cdc9712fe4ec3831117746320db38已error/released；HTTP仍UNKNOWN，response_bytes0，无模型候选，不重派。后续只读quota GET TLS握手超时，最后账单UNKNOWN。父pool.json已标dispatch_blocked，剩余第二批不自动分配；failure-reconciliation.json与[真实汇总](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-output-admission-qualification-batch01-2026-10-09.json)保存。302保护/142fixture/源码及封存原件保持，无新媒体/Build/MP4、未加载/提交/推送发布。所有具名Job已收终态；下一步核原请求与连接证据，不重新实现接收或开启平行Goal。下方是历史断点。

**2026-10-09 统一接收实施最新断点：** 第一单元intake@5/admission@1代码已接，67PASS/0FAIL/0skip（原Job `wc_job_8RjVLzueHKjdljuS`已取终态）覆盖规范化、正常Planning/Truth/Material加载、一次repair、凭据中断/原请求续接、冷verify、篡改及旧协议；两个早期测试FAIL保留并以测试模拟修正收敛，不削弱UNKNOWN保护。source `8f4743d0afdc5c22ad73c29157a7ca71f4d60fe6c389c66e1fb5407f4e73d0f4`/222生产文件，HEADdf0d3a30 dirty；302保护/142fixture和封存账本一致。原2071字节contains样本离线NORMALIZE可构造7槽位，旧@4消息原样，未改变失败评分。`tests/structured_planning_product.py::test_native_output_admission_lifecycle`已编写，但该原生执行调用被平台安全检查阻止，无Job/结果，未改路或重试。状态FIRST_UNIT_SOFTWARE_VALIDATED_NATIVE_VALIDATION_BLOCKED；不要重复实施、重派已完成Job或将旧原生证据转授。第二单元Material/Truth迁移待做，queries回退未启用，独立Reviewer未取得，新真实模型/媒体/Build0，无部署/推送发布，视频0/3。[具名结果](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-output-admission-implementation-2026-10-09.json)，私有`output-admission-implementation-2026-10-09/implementation-final.json`及原Session为续接依据。

**2026-10-09 统一接收设计：** 已核对近期9个资格首例（7输出合同/2实现工具），仅最新contains已证明可规范化解除首阻塞，其余不能任意过滤。原Task新增“模型结果统一接收方案：无损规范化与语义修复分离”，[审计证据](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-output-admission-audit-design-2026-10-09.json)。本轮仅设计，未改生产，source1dccfb0f/221文件不变，302/142历史保持，零新模型/媒体/Build，0/3视频。下一实施单元为统一接收接口+A-selection精确回显规则+raw/normalized凭据+details绑定/恢复verify；不重新实施关系审核、不重开旧批、不全局忽略extra。下面是历史时点。

**2026-10-09 当前断点：新关系审核资格首例FAIL，详细对账读取被平台拦截。** source1dccfb0f、intake@4/review@2，原Session不变；新目录`relational-qualification-2026-10-09`，manifest SHA4b292773032177adca8bc2eae3add6d7d54e2cf2d7bc4828b1c70dbfa8e562d7。Job `wc_job_MC1TtZ_P5MLVuUHA`已exit2，stdout为首例FAIL/actual_http1，观察token `wj3_06jGan3qWh1ApuM-.9.2.1`。不得重派该首例或剩余五例。后续诊断读取被平台拦截、无结果，未绕过；最终失败原因、原远端release、账本及收尾指纹待核，不能用早期A-selection pending快照推断终态。新媒体/Build派发0、无生产修改/部署推送发布/MP4。恢复相关访问后先核原结果和原请求，普通研发授权继续保留，不重新交接或从头实施。[具名记录](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-relational-real-qualification-2026-10-09.json)。下方为此前状态。

**2026-10-09 关系审核续接最新终态：** intake@4/review@2软件已完成收尾。原Job `wc_job_nRjMif4V1-gEiRlG`终态72PASS/1FAIL，测试修正@2必要性重审期望，旧失败保留。组合Job `wc_job_34_x-vuqCsrjcDW1`30PASS，原生Job `wc_job_2rK06q43JROe3AOj`1PASS/5回环HTTP，下游Job `wc_job_nTktTXy-wkdu5ie8`7PASS，全部结果已取回，不重派。B重复候选正文去重为共享表引用，七slot/56题总消息555762→391086bytes，逐项可逆且全部来源/Schema不变；未测真实成功率。source `1dccfb0f1c3a68602a45b4f28240f2eec818e070828a43f6db38d4fa820b630d`/221源、HEAD df0d3a30 dirty；302保护/142fixture/封存资格账本一致，旧@3四请求SHA精确重建。私有`planning-relational-review-2026-10-09/resume-final.json`与[公开收尾](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-relational-review-2026-10-09.json)为续接依据。独立Reviewer不可用；无新增模型/媒体/Build或部署推送发布、视频0/3。下一步只能使用新授权的有界真实Planning资格，不重做本次修复，不移用封存批额度。下方是此前时点。

**2026-10-09 最新断点：P3新真实资格失败封存。** 用户已授权的6例/40HTTP/2700秒新批实际首例FAIL：4HTTP/214263报告tokens/293.964秒，A-selection/details/B/repair各1，后5例未提交。直接失败repair引用1060>512字符；独立语义风险是A无视觉候选、B全32原始ACCEPT（12答复非法）且将图片报告绑定唯一BGM。4原run均ok/released，4参数流至捕获SHA一致，无新传输故障证据。新目录`p3-qualification-2026-10-09`账本closed，Job `wc_job_jsEJX8ikRlwLMi4U` exit2，不重派；source49b691…e18ff3/221源、302保护/142fixture均未变，旧池封存，quota99/97，Gateway active/lost/audit0。本轮无生产修改/加载/媒体/Build/推送发布，0/3视频。原Session及[具名结果](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-p3-real-qualification-2026-10-09.json)为下一入口；下方软件preflight待授权是此前时点，不得据此再次执行旧授权。

**2026-10-09 P3发布前核验最新断点：** 软件preflight已完成，source `49b691720f2a2086773aa6d28df61cac2fff9dfe66aaa7c970a6b51da1e18ff3`（221生产文件、dirty未提交），测试前后完整源码不变。302历史保护/142fixture和旧预算/节点终态报告指纹一致；31项当前源码收尾回归通过，Job `wc_job_OfQyFBAt8PqqGQmj` exit0/59.15秒已取结果。原七slot上下文56题、两批消息及空环境RPC容量离线检查通过，不证明模型能力；旧候选未决/optional未改。独立审查未取得，原实测池已封存，不自动启新批。新真实模型/媒体/Build均0、未部署或推送发布、0/3视频。下一步等待新的六例完整Planning资格范围明确确认及实际派发前配额/版本/未知执行预检，不再重做P3。[最新证据](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-p3-release-preflight-2026-10-09.json)，私有证据`p3-semantic-correction-2026-10-09/release-preflight-20261009/`。下方为旧时点。

**2026-10-09 P3软件续接收尾：** 实现完成，组合18 PASS；完整相关回归Job `wc_job_EgcxXayY1qY7qtvd`已exit1（319 PASS/2 FAIL），两测试期望调整后受影响路径Job `wc_job_NX0eZmJTyKWqpsZQ` exit0/15 PASS；未改生产代码再重跑全部，也不声称一次321全绿。原生生命周期Job `wc_job_BXOPA_K-pxjYgGmn` exit0/1 PASS，五次回环替身HTTP完成P3联合修复。原断线Job已经终态，所有本轮Job已收结果，不需要重派。Current State及[软件汇总](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-p3-semantic-correction-2026-10-09.json)是最新入口。生产文件快照围栏已核对，发布用source SHA和历史全清单核验仍待（本轮baseline读取被平台拦截，未绕过）；旧池封存，无真实模型/媒体/Build、无部署/推送/发布、0/3视频。后续先发布前核验和明确新真实资格范围，不重新实施P3。

**2026-10-09 节点对照最新收尾：** 用户已确认4HTTP/900秒额度，实际原表示与浅层各执行1格，总2HTTP/47240报告tokens；原表示4613bytes实际Schema PASS，但初版观测器要求[DONE]导致pre-SDK摘要缺证据停止（原测量不改）。仅修评测器clean HTTP EOF/tool_calls摘要判定，相关2PASS；剩余3格子清单绑定父账本及同绝对截止，浅层首格原生error/released/TOOL_REJECTED，后2格未提交。最后执行收尾475.598秒，所有账本保留封存，无重派/配额重置。生产source仍e6c7e125…9972b8，生产与Runtime未改，两个真实原run均released，无媒体/Build/新MP4。决策保留原表示，不接入浅层；下一步P3来源绑定的必要性纠错与未决分类仍须实施/验证。原Session不变；最后真实Job `wc_job_TWbaUjIyVOjUJx7G` exit2，离线Job `wc_job_SHNBXHpDKvqemmnf` exit0。私有`planning-node-contrast-2026-10-09/scope-final-reconciliation.json`与[公开汇总](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-planning-node-contrast-2026-10-09.json)为续接证据，不再从旧“待4HTTP授权”开始。

**2026-10-09 最新续接：** 已将边界定位至成片P0–P5方案写入原Task，并完成6次回环原生回放与4项合同回归。正确实际Schema载荷（含7680字节控制）未在SDK/Easel中变字符串；原失败raw在SDK持久层已为字符串且与Easel SHA相同，上游旧SSE缺失仍不归罪具体云端解析器。仅修改tests内的分流参数SHA、分片回放与浅层等价实验；生产source仍`e6c7e125…9972b8`，旧失败和预算封存不变，真实调用/媒体/Build新增0。未决项在B前拒绝及necessity变更被保护已离线复现，未放宽。下一关是明确新的4HTTP/900秒节点诊断授权并完成来源绑定纠错设计；不是重新跑旧批。证据位于`planning-boundary-replay-2026-10-09/`与[本轮汇总](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-planning-boundary-replay-2026-10-09.json)。当前3个离线Job均完成，无本轮未完成模型请求，视频仍0/3。下方保留此前时点。

**最新续接终态：** 原新增2批已执行完并各首例FAIL封存；源代码已至`confirmed-planning-intake@2`，source `e6c7e125ab66dc103a3f4fde6a986ce580ab5e174a14cb8812a550391c9972b8`，77项针对性验证PASS，真实出片0/3。两批实际文字HTTP共3，67292报告tokens；三个原run均released，最后Job `wc_job_oA0JjakGWyZQIWOW` exit2。最新问题：details slots是字符串且顶层缺项，视觉required降级、未供应素材误作未决。原失败不解码补项转成功，未满80HTTP不授权第三批。私有总账`continuous-development-80http-v1/authorization-ledger.json`已STOP_BATCH_COUNT_EXHAUSTED；[最终证据](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-intake-continuous-final.json)。末次全局Gateway/配额查询被平台拦截，未取得最新结果；不与已核实的原run终态混同。下方为此前交接时点。

**连续开发续接（2026-10-08）：** 当前Session `wc_sess_TVqbfxf7Z6k74Oz_` 已在原Task登记用户新增2批/80实际HTTP/5400秒授权。query/BGM intake策略和组合测试已改，尚未验证；此前14PASS只属于中间版本。启动定向pytest及新私有总账初始化被平台安全检查拦截，未返回Job/退出结果，本轮不绕过。无新的真实模型/媒体/Build，未加载服务。新真实批前必须先完成组合验证、固定源码及总账；不要重新执行已关闭的dd184d批。当前修改文件为planning_result_contract.py、planning_semantic_review.py、semantic_boundary_run.py、tests/test_semantic_planning.py及这次状态/Task记录，均保留未提交。

日期：2026-10-08。用户要求本轮执行收尾后写交接并暂停实施。本文是原 Goal 的交接记录，不建立新 Task 或第二条生产主链。唯一 Task 为 [自主首版 Task](../tasks/creator-autonomous-first-cut-2026-09-30.md)，当前状态汇总为 [Current State](../02_CURRENT_STATE.md)。

## 交接结论与停止位置

**最新停止点（2026-10-08）：** 原Goal恢复后已补完@9软件收尾，并实际执行独立清单`dd184d52…9d3d11`第0例。A-selection结构通过，A-details因六组query一中一英两条而违反合同，局部修复定位被Need根级错误阻断；另缺必要BGM。2实际HTTP/132.958秒，B/Truth/repair未进入，批永久FAIL/closed，后五例不派发。两个原run均已释放，无新未知执行；当前无待观察的执行Job。详见[失败汇总](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-source-view-real-failure.json)。

真实Job `wc_job_N-XmJrjiFrdCJ4OH`已exit2结束，禁止重跑。私有现场为`/Users/xgx/Library/Application Support/Easel/acceptance/autonomous-first-cut-2026-10-08/qualification-source-view-v1/`，包含原manifest、runs/run-00.json、实际HTTP账本、未改A原件journal、offline-diagnosis.json及final-reconciliation.json。后续从该已知失败与现有修复定位边界继续诊断，不从旧“能力门BLOCKED”或软件未完成状态重新开始；新真实批不得由本结果自动授权。

**接管更新（2026-10-08）：用户已在当前WebCodex会话明确恢复原Goal，原暂停解除，但真实派发仍须满足原Task前置条件。** 当前Session为 `wc_sess_TVqbfxf7Z6k74Oz_`。已核220源码/302保护/142fixture集合与摘要不变；复用run-053 276 PASS、排序后4 PASS及六例冷进程6/6（30本地替身HTTP）。补齐全量回归1034 PASS/5既有skip，0失败，723.599秒；原Job `wc_job_Et2HAi4fZWOjXb2t` 已完成，禁止重派。证据位于本页所列私有目录的 `webcodex-closeout-01/`；下方“正在收尾”保留为交接时点，不代表当前仍在运行。

当前正在收尾已启动的软件验证；完成后暂停。不得自行启动新真实模型批、服务加载、Material Supply 或视频 E2E。完整自主出片仍为 **0/3，Goal 未完成**。用户暂停优先于此前持续实施授权，须在用户恢复后再继续。

本轮实施的是 Planning @9 可逆输入视图：模型从明确原文位置选择素材语义，程序维护来源引用、冗余字段、快照和请求身份。Creator、Director、Material V1.3、Hypit 职责及 required、Rights、Match、Readiness、预算语义不变。不能把本轮软件通过当成模型可靠性或 MATERIAL_READY。

## 固定代码与线上状态

- 仓库：`/Users/xgx/Projects/Easel`，分支 `easel-studio`。
- HEAD：`df0d3a302ef59c6a5751f44be034fcc82a592f18`。工作区包含多轮既有未提交修改和删除；本轮没有 commit、push、reset 或清理这些修改。
- 本轮归档 production source SHA：`cc5587a4f6379e541cdec442808166d2041369ea6e320d892fedf4e3e2bb4f4e`，220 个生产文件。此 SHA 是工作区源码清单摘要，不等于 Git commit。
- 新 journal/checkpoint：`semantic-planning-checkpoint@9` / `semantic-planning-frozen@9`；输入视图与引用 policy：`planning-input-view@1` / `planning-source-selection@1`。
- 本轮**没有加载 Web / Gateway**。不能用 HEAD、源码摘要或离线通过声明线上已运行 @9。恢复实施时重新核验实际进程与加载版本。
- 离线 Gateway 测试 Runtime：`/tmp/easel-structured-runtime-20261008-diagnostics`，原固定摘要 `0759643ae25d9d776c51ed71532ba51a81c916c7606bd078bb73812bd1f4d7e6`。真实执行前仍须重新核对，不因路径存在即信任。

## 本轮改动及已确认根因

新增 `easel/integrations/planning_input_view.py`。完整原文、资格、scope、来源摘要、顺序与重复项可以确定性回建；正文引用使用 UTF-8 字节范围，原 authority span 保持 Python 字符单位。不能精确引用的独立原文保持原值；Voice 引用按真实目录生成，不强加预置旁白。

`semantic_boundary_run.py` 只对新 @9 请求启用该视图；旧 @8 及以前仍使用原消息、Schema、捕获与修复额度。details 绑定原 selection 字节摘要、还原后 canonical 候选、opaque headers、view/map 和 Schema。正式 verify 从冻结原输入重建视图并核原件；新 `SEMANTIC_INPUT_VIEW.json` 随既有冻结复制链携带。B 的语义题及共享一次 repair 保持。

真实历史输入已确认的风险包括：确认 BGM 要求与 Mode optional 默认同包、27 个物理行被三套编号误当镜头、空 continuity 仍让模型填值、重复哈希被误判成缺文件。@9 整理表示，**没有证明这些是全部失败的唯一原因**。必要性降级、字幕/旁白伪装 image 等仍是模型语义风险，必须通过后续独立真实评测判断。

本轮集成发现并修复实际持久化缺陷：JSON 排序改变 Voice 引用的遍历顺序，导致恢复时 lineage 摘要变化。scope 和 Voice 引用现确定性排序；新增持久 JSON 键顺序变化后 snapshot/schema 不变的断言。不能只靠内存往返认领恢复正确。

## 验证与证据

最终收尾已补齐：同源码矩阵276 PASS；全量1034 PASS/5既有skip；六例冷进程回放6/6，30本地替身HTTP。软件证据不代表真实模型语义通过。中间版本已完成新旧请求生命周期与重放 10 PASS、原生 Gateway 两阶段/复核/一次修复共 5 本地 HTTP / 1 PASS；这些是排序修复前证据，不能冒认最终源码验收。最终源码排序修复后正常 Planning→Truth、正式失败构建后的冻结复制重入、完整回建与来源映射 4 PASS。115 技能校验、compileall、本轮范围 diff 检查通过。

保留中间失败：首组 29 FAIL/26 PASS（包含外部 fixture 仍读旧消息格式）；适配后两条链仍 FAIL，精确暴露上述持久化身份缺陷；冷进程首试 1 本地 HTTP 后因 Provider fixture 错取完整用户消息最后一行而失败，修正为使用已解析 context。没有修改正式准入期望、扩大 repair 或恢复真实旧批。

公共结果入口：[本轮软件记录](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-source-view-software.json)。完整源码、JUnit、消息及清单在本机受保护目录：

`/Users/xgx/Library/Application Support/Easel/acceptance/autonomous-first-cut-2026-10-08/source-view-software/`

旧 @8 真实批 `qualification-staged-v2` / manifest `970ccb4e2e97118965e9c6cc5bb760809d373acc84cb1e9af9b052f64bb6464f` 永久 FAIL/closed：首例 1 真实 HTTP，后五例未执行，不复用剩余批次额度，不恢复计分。此前三次完整 Development FAIL 及 raw-stream 保护事故保留例外均保持原结论。

## 费用和运行边界

本轮新增真实模型 HTTP、素材采购/生成及 Build 均为 0。Goal 图片和预置旁白累计限额 ¥30，保守占额 ¥15，已知实际媒体费用为 0；未知账单不能据此按实际 0 结清。文字仅已购 MiniMax 套餐，禁止现金、API 余额、超额计费和付费回退；Hypit 仅允许核实免费的本地构建。此前授权继续保留，恢复后不重复问同项额度，但必须核实时套餐及账本。

## 用户恢复实施后的建议顺序

以下不在本次暂停收尾中执行；只有用户恢复 Goal 后才进入。

1. 读本交接、Current State、唯一 Task；核 HEAD/工作区源码清单与保护现场。不得覆盖现有未提交成果。
2. 若代码及测试没有变化，复用本轮验收，不为重复报告重跑全量。若改变实现，仅补受影响验证，并更新指纹。
3. 在新固定源码上制定独立真实 Planning 评测清单，复用现有 `planning_eval_run.py`、原三个主题和独立语义判据；不能重新打开旧批。软件回放没有测试模型判断。原建议硬上限为 40 实际 HTTP / 2700 秒，三主题各两次；Truth 可能多次 HTTP，40 是停止上限，不保证完成。
4. 提交前核套餐、真实凭证路由、无 pending/submitting/unknown 与活动旧 Owner、隔离 Runtime/工具/输入身份。首次合同或独立语义 FAIL、UNKNOWN 即停止该批。不得用人工改报告、删 Need 或补素材让失败变成功。
5. 真实资格通过后，按原 Goal 备份现场并加载服务，正常入口新作品沿同一 Delivery 继续 Material、Authoring、免费本地 Hypit 和输出绑定 Quality。开发限额及同根因两次修复失败的停止条件仍保留，不因本交接重置。
6. 最终固定同一版本，以三个不同主题全新作品连续自主出片验收：可播放 MP4、100% required coverage、正式 Rights/Match/Readiness、输出绑定 Quality、工程介入零。不得发布。

**恢复指令示例：**“恢复原稳定自主出片 Goal，先核对 Planning @9 交接及源码指纹，沿原 Task 继续；保留历史失败和现有费用账本，不重复跑无变化的软件验收。”
