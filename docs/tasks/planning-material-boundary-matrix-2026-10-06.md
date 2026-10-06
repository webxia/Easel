# Easel 模型输出可靠性统一治理实施方案

状态：**用户已确认并实施A–D；软件合同通过，现场保护FAIL，整体无例外验收不通过**。2026-10-06。Owner为Main，所属[素材层可靠供给Workstream](creation-latency-2026-10-02.md)。沿用原边界矩阵Task路径，作为统一治理与F1、G1、G2修复的唯一实施入口，不另建平行治理Task。

目标：统一治理**确认方案 → Preparation → Planning → Truth → Material入口**的模型输出，并在同一轮解决三个已知问题。复用已有矩阵、fixture和根因调查，仅补证据缺口。软件完成必须同时满足治理边界有效、三个问题关闭、合法路径与保护性约束无回归。

用户已明确确认本文全部默认选择并授权A–D。本文前八节保留获批设计；执行结果与现场异常见第九节及唯一验收入口。E批未启动，未重启服务、提交或推送。

## 一 既有成果与复用

第一阶段25行合同与集成矩阵已完成：**22 PASS / 1 FAIL / 2 CONTRACT_GAP**，pytest为24 passed / 1 failed。完整Expected / Actual、装配失败、根因和运行记录保留在[原矩阵验收](../acceptance/planning-material-boundary-matrix-2026-10-06.md)。PASS包含正确拒绝非法输入，不表示22条成功交付路径。

| 既有产出 | 本轮使用方式 |
| --- | --- |
| commit `36ead76beaeed02ce53d1580dc4f0fb56ddcd88e` | 调查基线；实施前对账工作树，不重置用户改动 |
| production source SHA `5f6e21a2fb301358c906291bbf4a811fa44ac986ace214a1c7ef687c10b0aede` | 沿用原文件清单算法；每批修复记录新指纹 |
| 三轮真实失败fixture与run-001至run-009 | 保留原件与历史结论；派生输入单独标明来源 |
| `tests/planning_material_matrix` | 唯一矩阵执行器，扩展原风险行，不复制harness |
| Owner → Preparation → Planning → Truth → persist → Supply → Observation离线集成 | 复用真实内部模块，只在外部执行边界使用替身 |
| 搜索1、接收1、观察1；prepare重入搜索/接收仍1 | 具名调用基线；Rights UNKNOWN、Gate MATERIAL_NOT_READY保持 |
| 原223个受保护运行文件、16个Creation对账 | 实施前重新只读采集当前集合，不假定未来数量不变，不操作真实作品 |

前三轮真实E2E的FAIL永久保留，旧作品工程恢复9/9不算独立自主验收。现有矩阵不证明真实Provider、生成、声音验证或模型语义泛化能力。

## 二 统一治理合同

借鉴Pydantic AI、Instructor、Temporal、LangGraph、Promptfoo的合同、有限修复、持久身份与评测思想，不引入运行时框架依赖。沿用Creation、Delivery、OpenClaw、Material Layer V1.3，不重写Domain、Provider或Gate，不增加公开HTTP路由。

### 基线与有意行为变化

分别记录**当前实际行为、已接受合同期望、具名真实证据**。当前会接受的错误不自动成为合法基线；第三轮混排稿的接受正是待修缺陷。原合法成功与原非法输入的正确拒绝均须保护。

有意改变已接受行为时，先记录旧/新行为、原因、兼容与验收，再完成前置复核。F1正文容器、G1查询解释、G2新旧规划区分在本文集中评审，不另开三套调查。超出本文的合同变化暂停受影响项并补充评审；三个已知问题未关闭时整体不得完成。禁止事后改期望、删案例或放宽门槛刷绿。

### 处理结果与状态推进

| 结果 | 条件及动作 |
| --- | --- |
| ACCEPT | Schema、身份、来源和业务校验通过，交给现有状态机继续核对Truth、预算、Rights等条件 |
| NORMALIZE | 仅处理明示支持且已证明等价的运输表示；保留原件，内存转换后完整重验，不改原Need或冻结正文 |
| BOUNDED_REPAIR | 已知可修合同错误且原阶段额度尚存，复用既有持久请求修复并重验；不新增无限重试 |
| REJECT | 身份/授权冲突、不能安全解释、必要事实缺失或修复耗尽，保留证据并进入既有停止/修订流程 |

身份、冻结输入、授权冲突优先拒绝，不能送模型补造。普通输出缺字段可在原阶段额度内修复；缺事实或许可不可以。pending、超时、提交未知是执行观察状态，核对原请求，不刷新额度。

使用应用层内部结果类型统一`outcome、stage、code、field_path、input_sha256、policy_revision`，可附原请求身份和脱敏证据定位。没有输入字节时摘要留空并说明原因。校验器继续拥有业务判断；结果类型只解释既有返回值/异常并明确路由，不另建状态机、执行账本或模型网关。

只在本轮五个阶段边界接入，复用现有日志、Attempt、agent call及修复记录。初始提示、结构修复和消费者复用同一合同定义与版本；不复制宽松Schema。普通日志不复制完整用户正文，不记录凭证。四类结果本身不授权状态推进。

测试结论独立使用`PASS / FAIL / CONTRACT_GAP / NOT_EXECUTED`，另标产品缺陷、测试缺陷、证据缺失。未定义合同不能硬判正确接受/拒绝，UNKNOWN不能算PASS。

## 三 三个根因的最小修复

已对齐方向：明确正文容器、旧query兼容为检索提示、新Planning必需要求文件而有效旧冻结记录可恢复。以下具体协议随本文统一评审确认。

### F1 正文与制作说明

责任位置是`easel/creator_proposal.py`共同解析、方案生成提示、保存/预览/确认入口及既有方案卡。保留五个栏目：创作表达、文案、分镜与节奏、声音设计、制作规格。

- 新“文案”栏目只允许一个标记为`text`的fenced block，块外只允许空白。说明、字数估计、配音参数和制作安排放入其他栏目。缺块、重复、未闭合或块外说明均不得READY_FOR_CONFIRMATION；块内类似栏目标题的文本不得分裂整个方案。
- 开始行必须为独占行的三个反引号加text，结束行为独占行的三个反引号。开始行后的第一个换行与结束行前的一个换行属于容器边界（LF或CRLF均可）；只移除这两处结构换行，额外首尾空行、内部换行、空格与中文标点逐字符保留。空正文拒绝；内部出现同样结束标记则按重复/多余内容拒绝，不猜测转义。不自动去引用符、删说明或重排。预览、确认SHA、冻结SCRIPT及Voice文稿绑定使用同一解析结果。
- 新结果用`easel-video-proposal@2`，保留原字段形状，script为容器内文本。确认入口重验合同和摘要，不只相信旧READY标记或客户端SHA；无效新回复不能让上一版继续显示为当前可确认稿。
- 有旁白放逐字旁白；无旁白有屏幕文案放逐字屏幕文案；纯无字作品沿用“无文案”表达并置于容器内，保持原无Voice语义，不合成该标记。三类合法路径单独对照，无旁白不等于无BGM/SFX。
- 未确认旧格式保留查看，下一次正常方案回复更新后才能确认，不自动迁移或确认。已确认旧作品继续按原proposal/SCRIPT/SHA读取，不按新容器重解析，不恢复失败作品；reopen旧稿只作可编辑参考。
- 无效输出保留讨论态并给出“正文与说明需要分开”等可理解原因，复用正常方案修订。默认不新增确认前模型语义审核、额外自动调用或新审核阶段。

容器解决结构混入，不能证明容器内自然语言语义正确。保留对已证实明确制作说明结构的检查，不能按“说明”“配音”等词的出现一概拒绝合法台词；相应合法正文必须有正例。Truth和冻结保护不放宽。

完成条件：第三轮原proposal及说明标题变体确认前拒绝；另将第三轮混排script原样包进合法text容器，仍须因已证实的制作说明结构拒绝，不能仅以原稿缺容器而认领F1关闭。结构检查覆盖独立说明标题、加粗说明标签与后续制作说明段；合法台词含同名词语须通过，不承诺识别任意隐含语义。合规新稿经保存、预览、确认、Planning后SCRIPT字节一致；旧已确认稿不变；旁白、屏幕文案、无字路径通过。单个parser测试通过不算完成。

### G1 query元数据角色

责任位置是NeedCompiler、visual contract及查询recovery消费者，共用一份纯函数解释；不改历史Plan，不给Domain增加Provider字段。

- canonical单query、canonical三变体、旧primary/alternate/relaxed三标量都是discovery hints，全部排除在filters、negative terms、视觉原文与required条款之外；intent、importance、来源限制不变。
- canonical三变体保持现有完整性、英文短查询、长度和互异规则。旧字段按primary/alternate/relaxed读取，每个存在值均校验，允许部分旧字段，按现有空白规范化/casefold去重；另有合法字段不能掩盖非法值。
- 保持现有最多4候选、截取顺序及末尾短英文优先的稳定排序；同类候选内保留recovery search_terms原优先级，不借本次治理改变已有最终排序。Need查询来源选一组：canonical三变体优先，否则旧三标量，否则单query，再沿用intent派生。canonical三变体存在时单query不再加入、旧字段仅校验；旧组存在时单query同样不加入。不同字符串不自动算业务冲突。BGM/Mode既有候选保留策略不变，并对最终Provider实参验收而非只验中间列表。
- 最终算法沿用现有顺序：按上述来源和既有BGM/Mode/上下文插入规则构造候选 → 空白规范化与casefold稳定去重 → 截取最多4条 → 沿用不足2条时的既有fallback → 对短英文做稳定优先排序。验收覆盖recovery为英文/非英文的对照，不虚称所有recovery都必为第一条。初始与修复提示只输出canonical；旧字段按兼容运输解释为检索提示，不把历史字段改写成正式对象，不删Need或扩张视觉要求。
- 旧query-as-filter请求不能命中新编译请求的搜索缓存。ProductMaterialSupply已有compiled intent SHA参与复用，优先复用该身份，测试证明query/filter变化确实失效；不新增全局policy或清库。若发现其他消费者未绑定有效输入，只修该局部身份并补针对性回归；无关素材及Rights/Match证据按原身份复用。

完成条件：canonical-only、legacy-only、混合、部分旧字段、重复/非法值都有确定结果；实际Provider边界query正确且filters不含query；视觉条款不变；相关缓存失效而无关有效缓存仍复用。

### G2 新规划与旧冻结记录

责任位置是产品Planning调度、PlanningIntegration.persist/load及Observation consumer。旧检查点兼容不等于新任务缺文件也可通过。

- 新正式产品Planning及旧未完成Planning都必须同轮交付`MATERIAL_REQUIREMENTS.json`。只有已有、身份与摘要有效的旧PLANNING_READY走恢复路径；文件时间或孤立状态字段不能证明是旧记录。
- 新产品Planning派发前由程序在既有Attempt记录持久登记`planning_contract_version=2`，重入不改身份。新persist写`easel-material-planning@2`，manifest绑定要求文件路径/字节SHA及各视觉Need的cache key，Attempt同时绑定manifest SHA。版本由程序控制，不进入模型MaterialPlan或Domain。
- persist设置PLANNING_READY前，校验Plan、全部视觉Need（含optional）、sidecar、Mode默认值与最终Need身份；cache绑定必须对应persist后的有效Need。Voice仍由程序绑定SCRIPT。写入期间输入变化则拒绝，不能部分合同成功就推进。
- 新缺失/无效sidecar进入已有一次structure repair，初始与修复使用同一必需文件列表和合同；额度不增加，仍无效则REJECT且Supply为0。没有视觉Need时明确交付空对象，声音仍走原合同；这不新增纯音频产品路线。
- v2 load核对Attempt/manifest版本和摘要、Plan revision、正文/Truth、sidecar与cache identity，任一版本标记缺失或冲突均拒绝。Observation在复用已有观察报告、合同cache或提前返回之前也必须完成当前合同核验，不能绕过load保护。损坏cache拒绝；单纯缺cache可从已绑定且有效sidecar确定性重建，不调用模型分类，不回落legacy key。sidecar缺失/损坏不能因cache尚存而放行。
- v1兼容仅限已有PLANNING_READY、Creation/Attempt/Plan与manifest状态/revision匹配、正文/Truth的既有摘要有效、无新版本登记的旧记录。v1原本没有manifest自身SHA，不要求回填或补造；v2则严格核对Attempt/manifest版本和已绑定SHA。原consumer可用有效当前cache、legacy key或在确无cache时按原政策分类。当前cache无效不能回落旧key；版本/摘要冲突不能降级。
- 未完成旧Planning采用v2前，先以原请求ID、原消息及原route观察旧pending初始调用或repair直到终态，不能用新提示覆盖原请求。终态产物再按v2校验；原repair已消耗而仍缺sidecar时直接停止，不因升级协议补发。未知结果未核实前不推进Supply。persist产品入口同样执行政策，不能只在Web拦截；省略参数不能让新产品Attempt写成v1。独立程序化Material服务保持原合法用法，但不冒充新产品Planning；已完成产品记录只走load恢复。

恢复决策固定如下，时间戳不参与新旧认定：

| 现场 | 先核验 | 允许动作与停点 |
| --- | --- | --- |
| v1 ready | 原Attempt的ready、Creation/Attempt/Plan身份、manifest状态/revision、artifact摘要、Truth ledger与冻结依据 | 原路径load/consumer；不回填v2摘要、不重跑Planning |
| 旧pending initial | 原请求ID、消息、route及未知执行状态 | 原请求观察至终态，再登记/验证v2；仅原structure repair额度未耗尽时可修复 |
| 旧pending repair | 原repair记录、消息及同一run | 原请求观察至终态；额度已占用，产物不满足v2则停止，不追加repair |
| 新v2 ready | Attempt版本及manifest SHA、manifest版本/Plan revision、正文/Truth/sidecar与合同key | 核验成功才允许复用报告/缓存或Supply；缺失/冲突拒绝，不降级 |
| 未完成且无活动请求 | 原调用/修复账本及冻结身份 | 登记v2后走既有执行；原额度不清零 |

v1只验证原本存在的字段；v2新增字段由程序在新执行中写入，历史缺失不能人工补证。没有有效旧ready或新协议身份的记录不得仅凭文件看似完整进入Supply。

完成条件：新缺文件正确修复/耗尽停止，合规新交付进入Supply/Observation，有效旧冻结记录恢复；伪旧、过期、删除版本标记、摘要错配拒绝；重入无额外修复或重复请求。

## 四 不回归矩阵和执行证据

保持原25风险行编号，扩展12（query）、20（sidecar）、21（proposal）及24/25集成参数，不另造第二套矩阵。原run-009不可覆盖；新结果注明本文版本及获批合同变化。只有现有测试未有效覆盖的风险才新增测试。

| 风险组 | 复用测试 | 必须保护或补齐 |
| --- | --- | --- |
| 确认与Truth | `test_creation_preparation.py`、`test_script_truth.py`、矩阵21至23 | 三类合法正文、新旧版本、原文冻结、错误来源/过期报告拒绝 |
| 合同与模态 | `test_material_control_contracts.py`、矩阵1至20 | G1查询优先级/filter/身份、G2新旧合同、全部历史wrapper/Unicode/path/null/audio边界 |
| 调度与恢复 | 矩阵24/25、现有Preparation/Delivery测试 | 真实创建/保存/确认/Owner至Supply/Observation连续交接；超时/重复回调/中断恢复原请求 |
| 权利与费用 | `test_material_rights.py`、既有生成/预算/授权集成 | 未授权、未知价格、重复占额、未知提交不能采购；旧授权不能扩大 |
| 无关素材能力 | 既有`test_material_*`及MiniMax确定性adapter测试 | Library/Provider、搜索/接收、去重、声音、Matching、Readiness及合法复用 |
| 下游保护 | 既有MATERIAL_READY endpoint/Owner集成 | 拒绝路径不采购/生成/Build；素材终点不进入Authoring/Quality/Selected Output |

每行记录基线版本、来源/SHA、合同依据、预期/实际处理分类、测试结论、状态变化、请求身份、调用参数/次数、持久副作用及证据位置。原件、派生变体、人工对照标明；证据不足不算通过。

集成运行真实内部模块，仅模型、网关、Provider等外部执行使用替身。替换掉Owner、persist、Supply或Gate的单元测试不能代替集成；静态检查/build也不能。使用隔离存储，不访问真实凭证或作品，保留JUnit/运行日志/机器结果并脱敏。

独立入口仍为`.venv/bin/python tests/planning_material_matrix/run.py`，不xfail/skip隐藏风险。补证阶段先固定期望再运行，不改生产。正式软件验收将稳定风险并入既有常规回归，矩阵复用同一场景实现，避免两套断言分叉。合同升级涉及现有测试调整时，保留旧版本兼容测试与历史证据。

## 五 实施批次与门槛

| 批次 | 工作 | 出口 |
| --- | --- | --- |
| A 复用与补证 | 复用已完成矩阵和根因；映射完整不回归清单；补合法正文、G1/G2政策及授权副作用缺口，只改测试/工具/文档 | 期望先固定，实际执行并归属失败；生产和真实现场未变 |
| B 前置复核 | Astra只读复核共同处理规则、新旧合同、测试分布与最小改动 | 风险有处置；用户确认统一方案后实施，不以末尾复核补票 |
| C 最小实现 | 接入应用层处理结果，依次修F1/G1/G2；同一Task/分支/证据入口 | 每个根因对应回归、原矩阵及完整不回归基线执行；未修已知问题如实列出 |
| D 组合验收 | 全部修复后组合集成、必要项目检查、源码和现场对账 | F1/G1/G2全关闭；范围内0 FAIL/0 GAP/0未执行，合法路径和保护无回归 |
| E 后续真实验收 | 独立版本/预算/运行复核，真实模型评测、Smoke、完整Material E2E | 各阶段单独授权，软件完成不自动启动 |

每个根因回归通过指该根因与全部原合法/保护场景通过；尚未修复的其他已知问题保留，最终D批才要求全部关闭。每批执行一次必要完整不回归，无新修改/风险时不重复相同验证。

D批运行`.venv/bin/python -m pytest -q`、完整独立矩阵、`.venv/bin/python scripts/validate_skills.py`、`.venv/bin/python -m compileall -q easel web scripts tests`、`git diff --check`。前端方案卡变化时增加frontend lint/build。既有skip说明适用性，本期必验场景不得skip。全量测试不能替代组合集成证据。

实施默认在easel-studio或其codex短期分支，保护现有未提交文件；不自动commit/push、重置分支或重启服务。并发生产改动先对账再固定受影响基线。回退只撤回本任务代码/政策，不删除运行证据或费用账本；旧软件不理解v2时必须停止，不伪装回v1。

## 六 后续真实验收

软件关闭报告逐项列F1/G1/G2行为、兼容、测试和源码指纹。任何一项未解决，整体保持未完成，不把它移出本期换取通过。

真实模型评测使用开发样本和独立留出，记录首次通过率、合法内容误拒、修复率、调用、耗时、费用已知/未知及工程介入。确定性测试不证明语义泛化，留出未通过不认领可靠性完成。

Material Smoke从正常新Creation到真实Planning、Material Supply及首轮真实Supply/Observation即停；停止机制须先经软件验证，不靠临时杀进程掩盖未知采购。Smoke PASS后另起新Creation，经正式Delivery到MATERIAL_READY。均不复用旧Plan/Need/素材/报告，不扩大授权、不倒算旧FAIL。

完整E2E要求required coverage=100%、Visual/Narration/BGM正式准入、Rights/Match/Readiness成立、Delivery正式MATERIAL_READY、AUTONOMOUS_DELIVERY=YES、ENGINEERING_INTERVENTION=0。代码修改、人工证据/放行、手补素材等工程介入立即令该轮FAIL，后续诊断不得倒算成功。终点停止，不进入Authoring/Hypit Build/Video Quality/Selected Output/发布。

前三轮预算不转授；第三轮¥10图片/预置旁白授权仍仅属于原Creation。真实评测、Smoke、新E2E各自启动前明确服务范围和预算。

交付沿用一个Task、一个矩阵执行器、一个软件验收入口：基线映射、合同裁决/复核、修复diff、根因回归和组合验收分阶段追加，原run-009及三轮FAIL不改写。真实验收按独立运行单独记录，不与软件证据混为一个PASS。

## 七 默认选择与确认范围

- 已对齐方向：正文容器、旧query兼容提示、新Planning必需要求文件而有效旧冻结记录可恢复、统一治理同时解决三个问题。
- 拟定默认：不加确认前模型语义审核；未确认旧格式正常修订后再确认；采用上述v2与局部兼容政策。前两项由本次“PLEASE IMPLEMENT THIS PLAN”明确确认。
- 确认本文后启动A至D软件工作；E批真实执行、预算和部署加载后置。Material V1.3的required、Rights、Match、Readiness和授权语义不变。

## 八 方案复核记录

2026-10-06 Astra只读设计初审为MODIFY，未运行测试或服务。已将最小修订纳入本文：F1容器内原混排反例与合法台词正例、精确换行提取；G1最终构造/去重/截断/排序及既有compiled intent缓存；G2恢复决策表、v1既有字段与v2新增绑定区分、Observation复用前完整性检查。该记录是文档设计审查，不替代A批新增证据后的B批实施前复核，也不认领修复已通过。

同日对修订版文档再次只读复核为 **CONTINUE**：满足本次实施文档交付要求，无新增必改项。结构合同不能证明语义泛化、A补证/B前置复核/组合集成仍须执行；不代表生产实现或测试已通过。

## 九 A–D执行交付（2026-10-06）

- A：保留原25行、三轮真实FAIL及run-001至009；补齐获批期望后，run-010为21 PASS/4 FAIL/0 GAP，全量基线731 passed/5既有skip/2新增合同失败。未通过项如实保留。
- B：Astra前置CONTINUE；冻结前分别按MODIFY补齐排序/来源副本、原pending对账、Attempt身份和CRLF保护，最终CONTINUE仅认可软件合同冻结。
- C：同一应用层结果、同一query解释、同一Planning v2绑定，关闭F1/G1/G2。未增加公开路由、运行时框架、Domain/Gate或授权规则。合法三内容集成的外部响应补交sidecar，并补副本SHA变化与wrapper来源绑定；内部链路保持真实。
- D：最终run-015为25 PASS/0 FAIL/0 CONTRACT_GAP/0未执行；全量738 passed/5既有bun缺失skip，115技能合同、compileall与diff通过。无frontend代码改动，不适用lint/build。测试、JUnit、源码快照和对账见[软件关闭记录](../acceptance/planning-material-boundary-matrix-2026-10-06.md#统一治理ad软件交付2026-10-06)。

`SOFTWARE_CONTRACTS=PASS / F1=CLOSED / G1=CLOSED / G2=CLOSED`；但`SCENE_PROTECTION=FAIL / OVERALL_EXCEPTION_FREE_ACCEPTANCE=NO`。首轮全量测试曾误登记两份历史Creation的v2元数据，现场未恢复；新增常规测试保护器并复跑证明后续不再变化，不能抹去事故。原FAIL、Plan/Need/素材/授权及workspace保持，事故四类路径已由内存反事实SHA精确定位。停在软件交付与事故记录，不启动E批，不认领真实MATERIAL_READY。
