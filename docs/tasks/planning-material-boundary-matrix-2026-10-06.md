# Easel 模型输出可靠性统一治理实施方案

状态：**A–D软件合同通过，历史现场保护FAIL保留；2026-10-07 R0–R3已实施并通过软件验收，未提交/加载新版本或真实评测**。原A–D日期2026-10-06。Owner为Main，所属[素材层可靠供给Workstream](creation-latency-2026-10-02.md)。沿用原边界矩阵Task路径，作为统一治理与F1、G1、G2修复的唯一实施入口，不另建平行治理Task。

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

## 十 后续固定版本与加载（2026-10-06）

用户另行授权commit与Web/Gateway加载，已完成：事故保留例外关闭（不恢复旧作品，历史FAIL不变），代码commit55af28fb/source cd314b19与run-015一致；原LaunchAgent加载及健康、空闲、Owner/现场对账PASS。没有真实评测/Smoke/E2E或push。具体证据见[唯一验收的加载节](../acceptance/planning-material-boundary-matrix-2026-10-06.md#固定版本与服务加载2026-10-06用户另行授权)。E批真实评测仍须样本、预期、调用上限、预算与停止条件，另行启动。

## 十一 R批：Planning单一语义源与程序编译（2026-10-07，实施前方案）

### 11.1 目标、状态与适用范围

这是同一Task在新失败证据后的结构修正方案；前述A–D软件结果、事故FAIL和真实运行结论全部保留。本节原为实施前获批方案；随后用户“设定目标并且按照文档进行实施”授权R0–R3，已完成软件实施与验收，结果见第十二节。新生产运行能力仍须固定发布/加载及真实评测验证，不将确定性软件通过扩大为自主素材交付。

总目标（用户2026-10-07对齐）：**消除Planning中模型对确定性派生结构的重复维护，并独立验证规划是否忠实保留已确认的创作意图；保持Creator、Director、Material Layer与Hypit的既定职责边界。**

“独立”表示语义预期和判断依据独立于被测编译器，不等于必须新增模型、Agent或状态机。

具体目标：消除模型独立维护MaterialPlan与要求sidecar、重复复制身份/原文/引用的责任。模型负责语义规划及分类，程序负责生成、验证并提交正式合同。范围终点为有效Planning/Truth持久化后，现有Delivery能决定进入Material Supply；软件集成继续覆盖首次Supply/Observation以验证消费者。Material V1.3的Domain、required/Rights/Match/Readiness和授权语义不变；不扩Provider、不改声音准入、不改生成服务、不进入Authoring/Build/Quality。

**采用两阶段语义处理，不采用分类原子重新拼装整个Plan的单轮新领域模型。** 两阶段共享唯一有效Need快照：第二阶段只为程序给定的原文单元添加分类，不重复提交需求正文。不是再增加一份由模型独立维护的正式合同。

### 11.2 根因证据与必须纠正的判断

| 证据 | 已证实问题 | R批处理 |
| --- | --- | --- |
| 前两轮wrapper、音频混入视觉、query/source/cache事故 | 模型产物重复引用与程序职责混杂并存 | 语义草稿只交一次；身份、来源、模态投影及所有派生产物由程序统一生成；保留既有模态/query修复 |
| 第三轮确认正文含制作说明，Truth停止 | 已确认语义输入不适合直接生产 | 保留F1正文容器、冻结正文与Truth；本次结构编译不能代替语义判断 |
| 新失败Creation `cr_bbe0db97318f45aea09dc839f3d9c916` / Attempt `fa_44695adb79746d294b2a6837c930fd5b` | 最终第9个视觉Need的sidecar引用不存在的 `constraints/subtitle_overlay_only` | v3模型接口不接受source_path或正式sidecar，程序从实际Need生成所有来源 |
| 同次持久repair记录 | 首错是 `needs.9.modality_spec.voice:value_error`；修复后才暴露路径错误 | 按阶段聚合能够独立判断的错误；去掉模型负责的Voice文本引用/hash等派生字段，减少串行暴露结构错误 |
| 矩阵的 `sidecar()` 辅助函数 | 正例由消费者使用的 `sources_for()` 构造，缺少独立答案及真实修复组合 | 保留装配测试，增加独立语义预期、真实错误回放、修复全过程和变体测试 |

最新失败不应描述成“同一路径错误修复一次仍未修好”；初始产物若无法从原归档找回，明确记为缺失，不能由最终文件反推初稿。只读检查已复现最终错误，三个登记Agent调用均ok/released，结构repair记录complete；这不表示合同成功。本轮未重新启动该作品。

现场引用为该Attempt的 `planning/MATERIAL_PLAN.json`、`planning/MATERIAL_REQUIREMENTS.json` 和 `materials/recoveries/planning-structure-repair-00b5d5318eda8678345d84d7754f79742bd5ad5118882281160c2ae2664b2728.json`。2026-10-07只读核对的SHA分别为：

- Plan：`a9c8bf4a6ec46d1f774a176a51cc95a8e9c9270dea3b6d850f3de103cd6137a7`
- Requirements：`64b6517918cff7170933a8f7fff7e93efda26642410f65f9b6d4e4bd3b0d3031`
- Repair：`ac416a305113f43350021a3d7b7219265342c6332578ac3f24eda1e994d58b95`

这些是本地现场摘要，不是已完成的新fixture或新验收。R0负责脱敏和隔离回放。

### 11.3 确定的处理流程

```text
正常确认方案（冻结正文/场景/声音意图）
  → Preparation与冻结上下文
  → A. 模型提交一份SemanticPlanningDraft
  → 程序schema/模态/输入绑定校验与默认值应用
  → 程序生成并保存唯一有效Need快照、来源表、分类单元
  → B. 模型对程序给定的单元做语义分类
  → 程序绑定分类，生成MaterialPlan/Requirements/manifest/cache
  → 现有Truth + 全部正式合同校验
  → 持久提交PLANNING_READY
  → 现有Delivery决定Material Supply
```

A、B和中间快照是现有Planning操作内部检查点，不增加第二状态机、公开HTTP接口或新的Material阶段。Truth仍使用现有正式入口；未确认草稿路径按原规则处理，已确认SCRIPT/SCENES/TREATMENT由程序提供并逐字节保护。不得为了凑齐五文件让模型重新写确认稿。

**A：语义规划运输合同 `semantic-planning-draft@1`。**

- 模型只写一个有界JSON草稿（`planning/SEMANTIC_PLAN.json`）；文件名由程序约定，不允许模型选择正式输出路径。Schema由实际类型生成，同一份Schema用于初稿、修复与消费者。
- `needs`保留现有MaterialNeed的语义：scope、role、intent、importance、duration_hint、desired_options、continuity意图、模态参数及检索短语。语义Need顺序保留，不自动合并、去重或删除重复表达。
- 模态使用现有image/video/voice/bgm/sfx判别类型；模型选择表达模态，程序从判别类型生成media_type，取消模型重复填写两套模态。scope和continuity的语义引用仍须对冻结来源验证；不能把模型写出的任意ref当作已存在来源。
- 不要求模型填plan_id/creation_id/attempt_id/need_id/context_refs、revision/hash、Voice text_ref/text_sha256、source_path、字符offset或正式sidecar。未知派生字段报错，不静默丢弃含义。Voice identity仍是语义选择，必须来自实际允许的上下文身份，不编造Provider音色或授权。
- query只在A提交一次，沿用G1共同查询规则。程序组装正式query结构；不由B再提交另一套查询。模态专属控制使用现有验证器，不能把未知声音参数自动搬到其他Need。
- 自由文本仍进入现有intent/约束语义，不通过新增“任意元数据”容器绕过检查。schema有效不等于语义正确；缺少明确输入依据、重要字段冲突或未知引用进入修复/拒绝。

**程序生成身份与来源。**

- Creation/Attempt/refs取当前可信上下文。对校验后的语义草稿形成规范序列化摘要，绑定冻结上下文摘要及编译政策版本，作为本次有效快照身份；对象键顺序无关，数组顺序和正文原字节有意义。
- Need ID按该快照身份和Need序号确定生成，Plan ID绑定Attempt与快照。相同快照重入得到相同ID；语义输入改变产生新快照/ID，不认领旧分类、缓存或正式准入。初始模型草稿没有生产Need ID，修复不得借重新编号隐藏删除需求。
- 程序应用已有Mode默认值和Voice冻结正文绑定后，再生成最终Need快照；来源表、分类与缓存全部引用这一份最终表示，避免默认值前后或JSON排序造成身份分叉。
- 复用 `sources_for`、`classification_units`、`bind_classifications` 的完整原文覆盖与软偏好保护。程序生成所有path/offset/来源索引；保留CRLF、中文标点和Unicode原字节，不做泛化Unicode正规化来掩盖原文变化。
- 冻结输入可供给的scene/event/continuity引用由程序列出，模型只选择已存在项；无法确定的引用必须明确报错，不凭猜测补齐。新增创意素材Need可以存在，但不因此获得新增身份授权、事实依据或预算。

**B：原文单元分类运输合同。**

- 程序为所有视觉Need（required及optional）生成全局唯一的本轮unit ID，并提供完整Need、完整来源、冻结上下文和允许的偏好引用。ID由程序映射回既有per-Need单元，模型不复制Need ID或建立自由Need映射。
- 模型只返回每个给定unit的 `kind`（required/preference/postproduction/unresolved）及允许的 `preference_source` 选择；不返回path、text、offset、摘要或query。
- 显式软偏好由现有规则绑定，其余语义由模型判断；不能把所有文本默认required或把叙事功能全部默认postproduction。混合语义无法在现有无损单元内可靠分类时返回unresolved，不删词、不重新拼句。
- 拒绝unknown/duplicate/missing ID、非法偏好引用、偏好升级、必要源动作转后期及任何不完整覆盖。全局ID到per-Need的适配必须经过既有 `bind_classifications` 与 `validate_compilation`，不能另写宽松校验器。
- B各批次结果先按冻结的全局→per-Need映射汇合；全部单元齐备后才对每个Need执行完整校验，部分批次成功不等于该Need成功。
- B成功后从相同来源和绑定结果程序生成现有canonical Requirements、缓存和manifest。文本及路径仅由程序读取原件写入；这从结构上消除模型引用不存在路径或抄错原文的输入渠道。

**语义保真边界。** 编译完整性只证明没有遗漏已接收的草稿内容，不证明草稿理解了全部用户要求。现有Truth验证事实和冻结稿，不冒充完整的需求覆盖审计。R批保留明确输入约束与原合法语义的独立预期；真实Planning Eval额外审阅confirmed proposal→Need覆盖、importance、偏好与后期分类。任何明确required被删除/降级均不能算通过。暂不新增一个“模型说已覆盖就放行”的生产Gate，也不以自动打分替代具名语义留出检查。

### 11.4 有界修复、诊断和持久提交

- 每个阶段返回内部结构化问题集合：阶段、错误码、草稿条目/字段或unit、预期、实际类型/合法引用集合、可否修复。普通日志只记脱敏定位及摘要，完整上下文留在受保护Attempt证据中。
- 一次收集所有能独立成立的schema与模态错误；JSON无法解析时不假造字段诊断；上游无效时下游标为NOT_EVALUATED，不把它误记PASS。不能为收集更多错误而先放行无效Plan。
- 初稿A一次；分类B按固定单元顺序分批，每批最多40个待分类单元，保留每个相关Need完整上下文。调用前依据现有网关实际输入/输出限制检查能否容纳；单个Need上下文无法容纳则明确停止，不截断要求或临时扩大token限额。
- 全部B批次在有效快照上确定并持久化，批次ID绑定快照、单元集合和顺序。已成功批次重入不重复提交，未完成批次仅观察原请求。纯声音Plan的B批次数为0。
- **整次Planning共享最多一次模型修复提交**，A/B不能分别领取新额度；沿用现有持久额度机制并纳入同一账本。A修复后才形成有效快照；B修复只修改失败的分类响应，不改有效Need快照。若存在多个B错误，合并可容纳的诊断执行这一次修复；无法在有界请求内修复全部问题则停止，不拆成多个新修复额度。
- 总Planning提交上限为 `1 + B批次数 + 1次共享修复`；Truth调用沿原流程单列计数及额度，不隐藏在该公式里。必须报告实际调用/等待/缓存复用和批次开销，不能宣称两阶段必然更快或更便宜。
- pending/submitting/unknown先核对原run。错误文案变化、服务重启、Owner重入、手动Retry或升级协议都不刷新修复额度。无法确认终态不新提交。网络重试与语义修复分别计数，沿现有Gateway观察/幂等机制执行。
- 复用现有Attempt存储，以同一快照为单位写派生文件，最后提交带完整SHA的manifest/ready标记。读路径先核对完整性；半写入或损坏只允许从同一有效快照确定性重建缺失派生件，已存在但摘要冲突不能覆盖或当缓存命中。没有有效提交标记时不得进入Supply。
- 四类OutputDecision保留：NORMALIZE仅是无语义变化的运输规范化，重新完整校验后才成为有效输入；ACCEPT也不独立授权状态推进。程序仍核对Truth、合同、身份和现有前置条件。B存在unresolved时停在Planning澄清，不以“格式合格”进入Supply。

### 11.5 版本与代码边界

新产品Planning使用版本3，manifest记录语义草稿摘要、最终Need快照摘要、分类响应/批次身份、编译政策版本及派生文件摘要。复用现有cache键算法，把上述会影响语义/绑定的政策与输入纳入其身份；不维护另一套检索cache。v3是应用层协议版本，不修改MaterialNeed@1或V1.3准入语义。

| 原状态 | 行为 |
| --- | --- |
| 有效旧v1/v2 PLANNING_READY | 按旧版合同只读加载，原字节及原身份保持；不得套用v3重编译 |
| 旧pending/submitting/unknown | 按原协议/原run对账，不能直接升级或重新派发；升级不是修复额度重置 |
| 旧失败作品 | 保留现场，不自动恢复、Retry、迁移或倒算成功 |
| 新获准产品Planning | 只执行v3两阶段，不因失败降级至v2模型手写sidecar |
| standalone Material调用 | 保持原公开入口与合同，不因产品v3强制新增模型调用 |

实现集中在现有Planning应用适配与Web调度、现有visual_contract分类绑定、PlanningIntegration持久化/load及其测试。允许增加一个应用层语义草稿类型/编译模块，职责为上述投影与编排；不修改Provider、Matcher、Rights、Readiness、BGM验证器、MiniMax adapter、Hypit/Quality。历史checkpoint副本路径仅增加v3显式校验/复制支持，不扩大制作流程范围。任何超出这些边界的必要更改先报告真实依赖，不顺手整治下游。

### 11.6 测试设计：沿用原矩阵，修正答案来源

保留原25风险行与旧版Expected/Actual记录，给新协议增加参数化变体；覆盖新风险确需新增行时使用同一执行器和同一验收入口，不以总行数固定质量上限。旧合同拒绝本次非法sidecar仍应PASS，不能改历史预期为接受。v3成功样本从获准语义输入重新编译，不能自动把非法旧输出清洗为成功。

| 风险组 | 输入及真实内部链路 | 核心断言 |
| --- | --- | --- |
| R1 历史回放 | 四份真实失败来源、有效旧v1/v2、脱敏原始外部输出 | 原因/身份可追溯；没有初稿的项不虚构；旧错误在原合同拒绝 |
| R2 合法全链 | 独立核定的视觉、voice、BGM/SFX、混合、纯声音、无字、optional、新旧模式 | 确认→Owner→Preparation→A→编译→B→Truth→持久化→首次Supply/Observation，内部模块真实 |
| R3 输出波动 | wrapper、额外metadata、缺optional、类型错、截断JSON、未知模态/字段、Unicode/CRLF | 四类处理符合预设；输入不丢语义；冻结原文无漂移 |
| R4 跨产物引用 | missing/duplicate/unknown unit、偏好错引、源文本修订、错误版本 | 不接受伪引用；每个来源完整一次；旧分类/cache不认领新输入 |
| R5 修复组合 | A多错→一次修好；A修好后B又错；B多错→一次修好；修后仍错 | 错误聚合准确；共享额度≤1；无法修好明确停止，禁止下游副作用 |
| R6 恢复与提交 | 每个检查点中断、超时、重复回调、半写入、摘要冲突、旧pending | 原请求对账；无额外提交/额度重置；无半成品READY |
| R7 意图保护 | 真缺required、required降级、偏好升级、动态动作转后期、无旁白/屏幕文字合法对照 | 独立语义预期保持；结构全覆盖不能替代用户要求覆盖 |
| R8 副作用与能力回归 | 未授权、Truth拒绝、Rights未知、预算限制、既有检索/声音/准入 | 拒绝路径采购/生成/Build=0；已有Material能力不退化 |

fixture分三类并标注来源：脱敏真实原件、单一变量派生变体、独立手写正确对照。正确对照中的来源、分类、required清单和最终关键语义由合同及人工核定，不能调用被测编译器生成预期。程序生成fixture保留为装配测试，不再单独承担连续集成成功证据。

变体采用固定种子、确定顺序，先覆盖单错，再覆盖已发生/高风险的两错组合，避免穷举无意义笛卡尔积。变形性质包括：对象键重排不影响语义；重复重入无新增调用；正文任意真实改字使旧绑定失效；删required/增加未知unit不能变绿；未知字段不能被NORMALIZE悄悄删除。查询结构和模态参数按原合同保持，不借运输兼容放宽。

所有集成测试只替换模型/Gateway网络、Provider和付费外部边界，实际运行内部Owner、校验、编译、Truth结果验证、persist/load和Delivery决策。Truth语义fixture只证明程序正确消费，不能认领真实事实判断。记录实际分支、请求身份、调用次数、状态变化、原文/现场SHA和副作用。

测试运行前将HOME/运行根/Creation/Attempt存储和数据库显式绑定临时目录，测试身份使用合成ID；真实fixture中的ID若为风险必要内容只作为输入，禁止成为运行存储定位器。保留现有写入保护，并在装配时断言所有可写根不落正式runtime；写入保护不是完整OS沙箱，不得这样宣传。运行前后对真实现场做只读摘要对账。秘密和真实runtime不复制入Git。

软件出口：上述必验场景0 FAIL/0 CONTRACT_GAP/0未执行，原合法路径与保护无回归；完整矩阵、常规pytest、技能校验、compileall/diff通过。前端未改不要求无关build；若确需前端改动则增加lint/build。既有环境skip单列，不掩盖新必验场景。

### 11.7 实施批次与禁止跳步的出口

1. **R0 证据与先失败测试。** 固定55af28fb及当前source SHA，归档最新真实失败的脱敏fixture和持久repair证据；核定旧合同拒绝、新协议正确输出及副作用期望。运行现状得到明确FAIL/未实现结果后再改生产。保留原run-015与事故记录。
2. **R1 运输合同与编译器。** 实现去派生字段的草稿类型、模态投影、身份/默认值/Voice绑定和来源快照；建立独立正确对照及编译不变量。仍不切换产品默认路径。
3. **R2 两阶段调度与持久性。** 接入B分类、共享单次repair、分层诊断、v3提交/load、旧版本恢复保护。真实内部连续集成与中断恢复通过后再把新产品默认协议切到v3；不在失败时回落旧协议。
4. **R3 软件冻结。** 全矩阵与项目检查，Astra复核实际diff及证据；源码/现场对账一致后固定版本。历史现场保护FAIL作为已处置例外永久保留；新的现场变化必须重新判失败，不能套用旧例外。
5. **R4 真实Planning Eval。** 独立授权并通过实时预检后执行下述受限评测；未通过不得启动Smoke。
6. **R5 Material Smoke。** 新Creation，经正式Planning到首轮真实Supply/Observation即停。必须预先验证停止能力，不靠杀进程掩盖unknown执行。
7. **R6 独立Material E2E。** Smoke PASS后另起新Creation，正式Delivery到MATERIAL_READY即停，严格required coverage=100%、声音/视觉正式准入、Rights/Match/Readiness成立、自主交付YES、工程介入0。

本节方案交付时未执行R批；2026-10-07随后授权的R0–R3软件结果见第十二节。R4–R6真实评测/Smoke/E2E仍分阶段单独授权，预算不从旧作品转授。

### 11.8 真实Planning Eval的最小可执行设计

- 使用正常确认/Preparation产生的冻结输入，调用正式A/B/Truth编排；运行在与旧作品隔离的评测工作区，采用正式代码和真实模型，供应、采购、生成、TTS及Build入口在评测执行器中禁止调用。
- 评测停止于“正式Planning/Truth合同可提交、现有Delivery下一步可进入Supply”的决策证据；不实际推进素材调用，不伪造MATERIAL_READY。评测装配先由确定性测试证明供应调用数恒为0。
- 固定16个合法主题：8开发样本、8独立留出，每个执行2次，共32次。覆盖视觉/视频/声音混合、无旁白/屏幕文案、含明确偏好、后期要求与动态源动作。样本与独立required语义清单在调用前冻结；留出不用来调prompt/实现，失败进入下一轮开发并重新选留出，不能修改原得分。
- 每次重复评测使用独立的隔离Creation/Attempt和请求身份，实际执行该轮A/B/Truth；禁止跨评测运行复用模型结果计作第二次成功。同一次运行内部仍按原身份恢复、等待和复用已完成检查点。
- 每次提交与修复均按 `1+B+1` 上限并单列Truth；预算以实际部署模型报价、输入输出上限和批次数计算，价格未知时不能猜测¥10足够。真实调用前需用户授权服务、总费用上限和批次；不足时标NOT_EXECUTED，不缩水样本后声称通过。
- 首次合同成功率、NORMALIZE比例、repair触发/成功率、最终合同成功率分别统计；分母为固定合法样本运行数，REJECT不算合法样本成功。另记录语义保真、误拒、调用、等待、耗时、已知/未知实际费用及工程介入。
- 首版进入Smoke的门槛：32次合法输入最终合同成功32/32；首次无需repair至少30/32；所有明确required语义保留、无错误授权或冻结原文修改、状态越界/供应调用均0；独立留出16次全部最终成功。无效输入保护由软件矩阵独立计分，正确拒绝不能提高合法样本成功率。
- 这些是本次发布的小样本验收门槛，不是长期可靠性概率保证；记录样本规模和置信局限。任何语义错误、源码变化、人工修写正式证据均保留本轮失败，修复后以新固定版本开启下一轮，不倒算。
- 预检使用实时任务与持久账本（含runtime_release）核对unknown/pending/submitting及Owner下一步，不能仅看健康端点、旧快照或Delivery failed标签。记录commit/source SHA与实际加载证据。历史已处置事故FAIL不要求擦除，但必须附处置记录且当轮现场无新增变化。

### 11.9 开源参考与不引入的内容

2026-10-07只读查阅官方仓库文档；以下链接跟随上游main，是设计参考而非本项目已安装版本或验收证据：

- [Pydantic AI结构化输出与验证](https://github.com/pydantic/pydantic-ai/blob/main/docs/output.md)：复用“类型Schema、应用验证、具体ModelRetry反馈”的思路；JSON合法不证明业务语义。Easel沿用已有Pydantic及OutputDecision，不新增Pydantic AI运行时。
- [Instructor重试](https://github.com/instructor-ai/instructor/blob/main/docs/concepts/retrying.md)：明确SDK网络重试与输出验证重试不同，不能让层叠重试隐含放大实际调用。Easel继续使用持久Gateway身份与统一额度，不引入额外重试框架。

不以迁移LangGraph/Temporal或新增Agent替代本次职责修正；这类框架也不能自动保证原文、required语义或预算正确。必要能力已在本仓库的分类绑定、持久调用和Gate中，优先复用。

### 11.10 Astra设计复核与交付判断

Astra首次意见为MODIFY，要求用两阶段复用现有分类绑定，避免分类原子IR重建Plan导致“错误语义也天然一致”；同时明确总调用上限、共享修复额度、旧pending协议及独立测试答案。上述修订已纳入本节。2026-10-07最终文档复核为 **CONTINUE**；按建议补充B批次完整汇合及每次重复Eval独立身份、禁止跨轮模型缓存计作重复成功。该结论仅认可方案可实施，不是软件验收或真实执行授权。

本方案能消除的故障源：模型自由生成sidecar路径、重复复制原文、重复维护正式ID/摘要、双份query及生产文件之间的引用关系。仍须真实评测的风险：语义遗漏、错误importance/分类、模态选择、模型拒绝或服务不可用。根本性解决的验收依据是职责已转移且真实证据通过，不是保证“从此任何输入永不失败”。


## 十二 R0–R3实施完成与软件停点（2026-10-07）

**R0–R3=SOFTWARE_ACCEPTED；R4–R6=NOT_EXECUTED。** 原25风险组与run-009/run-015保持，唯一执行器扩展至36风险组/53参数化场景，最终run-017 **53 PASS/0 FAIL/0 GAP/0未执行**。全量787 passed/5既有bun缺失skip（不属于必验矩阵），115技能/compileall/diff通过；Astra实际实现两轮MODIFY落实后CONTINUE。没有修改Material V1.3冻结语义，旧确认/v1/v2恢复路径保持。

| 批次 | 已完成内容 | 结果 |
| --- | --- | --- |
| R0 | 固定55af28fb与cd314b19，第四轮原件脱敏/来源与原SHA，旧合同拒绝回放和新协议未实现先失败 | 原1 PASS/1 FAIL记录保留；未虚构缺失初稿 |
| R1 | `semantic-planning-draft@1`、程序Plan/Need身份、模态投影/默认值/Voice文本绑定、可信来源、完整单元及独立预期 | transport/分类错误拒绝，正例原文/importance/偏好/后期保持 |
| R2 | A→B共享有效快照，整次一次repair，未知原请求恢复，v3 persist/load/cache/报告复用保护、副本显式身份绑定 | 正常@2产品链进入Supply/首轮Observation；旧合同不自动升级；纯声音B=0 |
| R3 | 全矩阵/全量回归/Astra/源码差异与现场对账 | 软件通过；新source指纹冻结但未commit/加载服务；历史FAIL保留 |

Astra暴露的首次拒绝/重入放行漏洞、有效子字段随错误字段被改、旧执行误登记及真实Gateway证据缺失均已修正并回归。修复不能重写有效intent/importance/模态/策略/约束/声音子参数，不能删Need；坏字段可合法纠正。B仅修受影响批次且原草稿不可改。

Voice v3实际采用程序枚举的 `creator_context.voice` 或具名上下文identity引用，验证source/reference/参考素材/consent。普通Treatment文本不制造声音身份或授权。无可绑定来源明确停止；旧v1/v2不迁移。B上下文256 KiB是本应用明确停止上限，不宣称所有模型/网关均可容纳，真实Eval需记录实际限制和费用。

隔离连续集成Gateway fixture为Preparation/A/B/Truth各1，Local搜索/接收/Observation各1，完成重入搜索/接收保持1→1；纯声音Planning1次，40+1跨批加repair为4次。真实Gateway内部适配器仅RPC替身的提交超时/释放超时均保留原run/request SHA，A/B提交两次，不重复提交。素材仍MATERIAL_NOT_READY，不造准入。

源HEAD **55af28fb62bf4bd0d194b372101a55b05a48a051**；验收工作树202文件SHA **0907c35cf4ee98254ac0a598f924d7b757b4aaf29cc24d1ac1d3f234d5e65217**，完整文件清单及确切生产diff已保存，未自动提交/推送。R0至最终257现场文件未变、原19历史fixture未变；新增后24fixture矩阵前后不变。历史事故FAIL例外和四轮真实失败不改写。

[唯一验收及完整证据](../acceptance/planning-material-boundary-matrix-2026-10-06.md#r0r3-单一语义源软件验收2026-10-07)。本次不主动重启/加载服务，实际运行版本未重核；真实模型/Provider/采购/生成调用0、费用新增0、新真实Creation 0。停在软件验收，下一步单独固定发布与核验加载，然后冻结独立Planning Eval样本/语义预期/预算并执行R4，合格后才R5 Smoke、R6独立E2E。


## 十三、R4 运行处置与评测器缺口（2026-10-07）

用户授权并固定99b3ca83/source0907后，评测工具64项离线矩阵及12项针对性装配通过、Astra CONTINUE。真实第0项Preparation只提交1个run，原生异步观察进入`observing_execution`，冻结runner遗漏该非终态并误记FAIL。保留失败并停止本批；原请求自然ok/runtime released、四草稿原生校验PASS，无Attempt/A/B/Truth/Supply。生产及冻结工具首次真实调用后未改，工程介入0；不能从该结果判断Planning合同稳定性。现场和费用见唯一Acceptance，完整原始记录仅在受保护本机目录。新增raw-stream日志丢失事故已获用户保留例外，历史FAIL不变。

后续最小修正范围仅评测工具，不改Planning、Material或Gate：

1. 用原生持久agent_calls/status/runtime_release与Delivery决策识别非终态，覆盖submitting/pending、observing_execution、execution_uncertain、runtime release pending。原请求未知不得重提交。
2. 评测器驱动现有Owner的检查点循环；一次observe_agent完成不是评测完成。原run终态后可以沿同一Creation/Attempt/请求账本继续正常下一阶段，直至正式persist+load+TruthPASSED并在Supply入口前停止。恢复轮询不计作第二次独立评测，也不刷新repair额度。
3. 增加真实内部Owner→原生Gateway adapter（仅RPC响应替身）的异步生命周期回归：accepted/pending→observe仍pending→同run成功→释放→prepare继续A/B/Truth→正式cut；分别包含terminal error、lost、wait超时、release未知、客户端重启。断言各阶段真正agent提交仅1次、ID不变、repair不刷新、Supply恒0。
4. 墙钟覆盖整个生命周期；阶段调用、Gateway独立run、观察RPC、模型响应、工具次数分开计数，不能将客户端数秒当成模型耗时。
5. 沿用同一矩阵及验收入口，完整回归后冻结新工具指纹，以独立新批次从32个新Creation重跑。当前失败批次永不修改为PASS；软件/预算/服务范围发生变化时按原规则处理。

本节是失败后的具名处置与最小修正范围记录，**本批没有实施上述修正或启动新真实批次**。真实Planning仍未验证，Smoke/E2E不启动。

### 13.1 异步前置回归发现生产缺陷（2026-10-07，STOP）

上段保留首次失败处置时的状态。后续仅修改评测工具：按持久 `agent_calls/status/runtime_release` 分类，驱动原生Owner检查点循环，客户端超时保留可恢复原请求，归档每次客户端执行和累积墙钟。未修改生产代码、旧批成绩或历史现场，也未启动新真实批次。

新原生异步集成复现了一个生产缺陷：`accepted/pending → Preparation ok/released → A ok/released → prepare重入` 后，A请求因JSON对象键序变化被拒绝。四种正常恢复变体（accepted、wait timeout、release pending、客户端重启）都失败于同一根因；lost保持原请求和terminal error停止两个保护路径通过。

因果链：`creation_preparation._persist_snapshot`把规范排序字节写入冻结快照，却返回原始内存bundle；首次Planning接收voice对象顺序 `tone,avoid`，重入从冻结快照读取为 `avoid,tone`。`source_catalog`原样嵌入该对象，A消息 `json.dumps`未稳定排序；`invoke`逐字节检查持久message及hash。解析后的完整A JSON相等，原始请求文本SHA不同，因此在读取原A终态结果前被拒绝。既定身份校验不能放宽；错误在请求构造不稳定。

同一矩阵run-004 **66 PASS / 4 FAIL / 0 GAP / 0未执行**；run-005仅增加只读诊断证据归档，6项异步场景 **2 PASS / 4 FAIL**。全量 **801 PASS / 4 FAIL / 5既有skip**，四个新增FAIL同根因；115技能、compileall、diff检查通过。生产0907/commit99b3、257旧现场及25fixture均未变。Astra只读复核 **STOP**；不需要再花真实模型费用证明此软件缺陷。新真实调用/供应/生成/TTS/Build/费用=0。

后续统一最小修复方案（本阶段未实施）：

1. 对新请求A以及同类B/repair使用稳定JSON序列化，保留字符串原字节、Unicode内容、数组顺序和既有scope/hash校验；不能通过排序fixture规避。
2. 核对首次使用与冻结重载是否代表完全相同的对象；优先消除请求构造差异，不修改确认稿、Need、Material合同或Gate。
3. 既有持久请求message/hash/run identity与repair额度保持原件，不覆盖或迁移，不恢复历史失败作品。需要恢复旧非规范pending时，必须另行定义兼容合同；不能拿重算摘要或新身份冒充原请求。本次旧批不恢复。
4. 让上述六个异步场景实际通过，并覆盖对象键序等价变化、真实字段/正文/route变化仍拒绝、A/B/repair及跨批重入；每阶段提交一次，未知只观察原run，repair不刷新，Supply恒0。
5. 完整矩阵和不回归验收无FAIL后，固定新的commit/source/tool指纹、重新检查服务加载与空闲状态，再开新32项独立Eval；旧批FAIL不改，Smoke仍后置。

[完整脱敏证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/async-preflight-summary.json)及[唯一验收](../acceptance/planning-material-boundary-matrix-2026-10-06.md)。当前R4停止于前置验证，不认领模型合同失败率或素材就绪；生产修复及新版本真实运行尚未实施。


### 13.2 后续独立软件修复与新批冻结（2026-10-07）

旧99b3版本R4已停止，旧批FAIL及§13.1证据保持。按统一治理及“后续修复使用新固定版本重新开始一轮Eval”执行独立软件阶段；不在旧批中救场计分。

生产修改仅semantic_planning.py中A、B、repair三个JSON序列化增加稳定键序。字符串/列表/冻结文件未规范化，invoke原message/hash、scope/route、身份和共享repair保护未放宽。不迁移旧非规范记录，不恢复失败Creation，不声称旧pending兼容已修复。

同一矩阵run-006 **70 PASS / 0 FAIL / 0 GAP / 0未执行**；全量 **805 PASS / 5既有skip**（58.20秒），29项针对性回归通过，115技能/compileall/diff通过。原生异步Preparation/A/B/Truth各提交1次，超时/release未知/客户端重启均原run恢复，lost保持未知、terminal error停止，Supply=0。257旧现场和25fixture未变。Astra复核CONTINUE，无新增必要修正；仅允许固定新软件后受限R4，不授权Smoke。

评测器版本从显式--fixed-commit/--fixed-source绑定，已有roster不能换版本；保留四类结果、持久检查点和独立语义审核前序门槛。新批使用独立目录及32个新Creation，预算仍只用已购文字套餐，unknown及25%保守余量以下停止，无付费回退。真实运行前另核实际加载、实时任务/账本与raw-stream原路径备份。此处只记录软件通过；新commit/加载及真实结果以唯一Acceptance和当前状态补记。


### 13.3 新版本真实第0项失败：repair目标合同缺口（2026-10-07，STOP）

新版本a7f7ccfe/source327842已提交并安全加载，原16主题及oracle未改，batch02以32个全新Creation独立冻结。实际第0项完整墙钟202.975秒：Preparation原run成功（102.624秒），A成功交付草稿（64.070秒），Schema因5个policy布尔值不符合dict[str,str]触发唯一repair（22.496秒）。repair网关成功不代表正式交付成功；正式消费者仍读取原A而拒绝，B/Truth未执行。本批立即FAIL并停止，31项未执行。

真实repair独立会话只有一次write，目标为Gateway默认workspace/SEMANTIC_PLAN.json；请求只提供受控basename，没有Attempt workspace或绝对路径。正式Attempt/planning原文件仍含布尔值，A.raw与消费者repair.raw相同；误写文件policy已为字符串。两份原件与各SHA、请求账本和3段脱敏会话完整保存，未搬入正式目录，不作人工救场。错误目录是否原先存在未知，不认领全Gateway workspace无损；257受保护正式旧现场、25fixture、冻结正文和固定源码/工具均未变。

根因分类为MODEL_OUTPUT（初始policy类型错误）+STRUCTURAL_CONTRACT（repair目标身份缺失）。现有fixture从闭包root或Creation中补路径，真实独立会话没有同等信息，故70PASS软件结果未覆盖此风险。Astra复核STOP；STATE_VIOLATIONS=1（repair输出范围越界），WORKFLOW_STATE_VIOLATIONS=0，ENGINEERING_INTERVENTION=0，Supply/Provider/生成/TTS/Build=0。Prep/A/repair各1，共19个模型assistant响应、29工具、17次原请求观察，没有重复付费提交；套餐5小时99→98%、周99→99%，共享账号实际账单未知。

后续最小方案（尚未实施）：

1. A/B repair消息必须包含当前Attempt workspace及程序绑定的全部绝对输出路径；路径对应当前Attempt/planning，内部持久记录仍用受控basename。不能让模型猜cwd、复用A会话或自己建立路径绑定。
2. 保持request hash、独立请求身份、共享一次repair、scope/route、冻结原文及有效Need语义保护；不放宽policy Schema，不迁移本次请求，不移动误写文件救场。
3. 扩展同一原生异步集成，A与B repair均为独立会话，默认cwd故意不同；外部fixture只能从实际请求解析写入位置，不能从闭包root或Creation补足信息。覆盖accepted/原run恢复/repair一次/正式消费者取得新产物/Supply0。
4. 完整回归通过后另固定新版本、新工具与新32项批次；本批FAIL永不覆盖。当前只保留现场与诊断，不启动后续Eval或Smoke。

[新批结构化报告](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch02-actual-run-summary.json)与[Astra复核](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch02-astra-review.txt)。


### 13.4 repair路径绑定独立软件修复（2026-10-07）

§13.3旧batch02保持FAIL/STOP，不恢复、不搬移误写原件。后续独立软件修改只收回repair输出路径：原始Attempt先交现有store验证，再取得规范绝对root；派发前检查planning目录和固定A/B目标非symlink、严格位于本Attempt。程序提供attempt_workspace/output_paths，与targets一一对应并纳入原持久message/hash。复用一次修复额度，Schema、身份、有效语义、冻结原文、Material/Gate均未放宽；此检查不构成外部OS沙箱。

新增A/B原生异步repair只解析实际请求，默认cwd不同，不能从Creation或闭包补路径。修前run-007 **6 PASS/2 FAIL**复现真实根因，源码/现场不变；修后同一完整矩阵run-008 **72 PASS/0 FAIL/0 GAP/0未执行**。正式消费者读到修复输出、独立run恢复、共享额度一次、Supply=0；另有root/planning/target symlink拒绝派发保护。全量 **810 PASS/5既有skip**（59.88秒），语义针对性72 PASS、115技能、compileall/diff通过，257旧现场和25fixture未变。Astra前置MODIFY已落实，最终CONTINUE允许完成检查后固定新版本/安全加载/另起32项R4，不代表真实PASS或Smoke许可。

batch03沿用原16主题和独立oracle，但全部Creation/Attempt/请求重新建立。预算仅已购文字套餐，无现金/API余额/超额/付费fallback；先实时idle对账，再停止服务并精确备份实际raw-stream路径后加载。旧批证据追加摘要和新软件JUnit均保留；新固定SHA/加载/真实成绩由唯一验收另记。本节记录软件阶段完成，真实评测尚未开始。


### 13.5 batch03：路径修复有效，但A→Compiler合同仍失败（2026-10-07，STOP）

固定commit `63da1b009bf349d82315acc180c9d33dc4d8b86b` /生产SHA `61b6a75e65b214e61d0fa6da693cb97ed4dd722c667fe3becd9f760945ff807b`，安全加载后另起32个新Creation，原16主题和oracle未改。第0项 `cr_c7e2a3b69b7c4d0fb2edea1a1581791a` / `fa_7a3298e7723034c95a855e9e5b020c90` 正常Preparation成功，A policy含对象/布尔而Schema要求字符串，触发一次repair。真实write确已写入本Attempt绝对输出路径，正式消费者读取新的policy字符串结果，证明§13.4路径修复起效。

随后仍FAIL；A Schema允许任意constraints值，但NeedCompiler把非具名例外作为标量检索filter：`constraints.must_contain`数组被拒绝；另一Need的 `continuity_refs.ref=production_brief.text_overlays` 不存在于冻结catalog（continuity为空）。初始policy Schema错误使compile检查未执行，repair只收到policy问题；一次额度耗尽是最终停点，不是根因。纯只读离线compile复现这两项错误，未改正式文件、Schema或额度，未触发新模型调用。文字叠加被列为required image亦属后期污染素材风险；未到B/Truth/正式语义评分，不宣称完整语义结论。Astra STOP；不得增加repair、删除约束/required或迁移本批请求。

本批 **1 FAIL /31未执行**，held-out0/16，最终合同0/1执行项（0/32计划项）；墙钟205.748秒，Planning约156.954秒。Prep/A/repair真实run各1、全部ok/released；创建至模型终态分别46.722/117.166/25.444秒（created_at秒精度）；B/Truth0。24模型assistant响应、25工具、17次原run观察/17pending检查点；5应用callback包含2次缓存原请求恢复，不是5次付费派发。Supply/Provider/生成/TTS/Build0，state violations0、ENGINEERING_INTERVENTION0。文字套餐5小时98→97%、周99→98%是共享账号比例；实际账单未知，不能把Gateway零usage/cost当作免费证明。

257旧现场、25fixture、batch02所有原件、固定source/tool/HEAD及本次SCRIPT均不变。重启前386041字节raw精确备份，停止后52235字节完整保护归档及脱敏副本；3段真实会话、原A/repair原件、请求账本、故障现场及各SHA保留。实时对账无pending/submitting/runtime-release pending，Gateway active/lost/audit0。本批立即停止，未执行第1项，未改生产代码/产物、不认领Smoke。

后续独立软件批次的统一对齐范围（当前只规划，未实施新的合同变化）：

1. **一个输入合同覆盖整个编译链。** 盘点A Schema、compile_draft、NeedCompiler、modality约束、continuity catalog及visual clause compiler；给每个字段固定生产者、消费者、合法表示与拒绝理由。不能仅用Pydantic通过替代完整编译可接受性。
2. **语义与检索控制分开。** 列表主体/数量/禁令须有明确语义承载及可追溯正式clauses；不能丢弃列表、未经等价证明拼成Provider硬filter或通过删除required换取合法。优先采用有限语义字段与程序派生结构；若涉及Semantic Draft合同变化，先形成版本、兼容范围、边界和语义保真验收再复核，不改变Material V1.3。
3. **引用由冻结来源绑定。** 模型仅选择实际提供的语义来源token，程序构造正式引用。continuity catalog为空时不能交付引用；unknown引用保持拒绝。不得虚构catalog条目来接受当前错误。
4. **后期要求保留原归属。** 正文叠加等要求保留可追溯后期义务，不制造额外素材采购Need，也不能静默删除创作要求。没有正式语义评分的当前raw风险只能作为fixture和预期对齐素材。
5. **一次repair包含完整安全诊断。** 尽可能分别汇总可以独立核查的Schema及跨字段错误，避免policy首层遮蔽其他问题；无法安全分析的范围须明示。保持共享一次额度、未知请求只观察、冻结正文及有效语义保护。特别补dict/list有效要求的保护，不能利用旧保护跳过容器值来删除要求。
6. **先离线真实证据，后原生异步链。** 复用本批初始A、repair与冻结catalog建立脱敏fixture，扩展同一矩阵，覆盖多层同时错误、列表要求无丢失/不误升filters、unknown引用拒绝、后期保留且不采购、合法路径不误杀；先固定Expected/Actual再修改实现。完整回归/Astra复核/固定版本/安全加载后，才重新独立32项R4。旧FAIL全部保留。

[结构化真实记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch03-actual-run-summary.json)与[Astra STOP](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch03-astra-review.txt)。当前目标32项完整真实Planning Eval仍未达成，READY_FOR_MATERIAL_SMOKE=NO。

### 13.6 A输入边界统一最小对齐设计（独立软件批，2026-10-07）

本阶段不恢复batch03，不改变Material Domain、canonical Requirements或Hypit职责。以当前已有消费者合同为准，收紧新请求的**发布Schema和说明**，不新增运行框架、HTTP或状态机，不把未知structured constraints兼容为filters。

- **新请求的发布Schema。** 使用现有SemanticPlanningDraft/NeedSpec模型构建请求Schema，但constraints只能表达现有标量检索控制、合法voice_delivery和显式视觉偏好；按模态限定例外。主体/数量/禁令写入唯一intent描述，不能复制成未知列表filter。scope/continuity/voice引用仅限本轮实际catalog。明确后期字幕/布局留在冻结SCENES/TREATMENT及已有intent.function/后期clauses，不额外产生采购Need。保留现有可选policy字符串Schema，通常省略以使用程序默认strategy；不得用policy制造授权/预算。实际合法policy仍进入原身份计算和保护，已冻结v3按原合同校验，不迁移产物。
- **完整且不伪造的诊断。** 顶层Schema错误时仍独立检查结构已合法的各Need；同Need的来源/模态/检索检查能安全独立进行时一并收集。不能为了诊断把坏字段默认化后产出正式Plan。最终仍只有全部Schema、来源、编译检查通过才生成Plan；已有合法草稿ID/字节/派生逻辑不改变。原始JSON不能解析的项只报解析问题，并明确不能检查其余层。
- **修复语义保护。** policy部分错误不能允许修改其合法字符串子项；未知dict/list约束也不能通过删除/改写让repair变绿。没有定义安全等价转换时保留原语义容器并拒绝，不能自动转filter或散装拼句。具名voice控制等已有修复例外沿原验证器处理；unknown来源仍拒绝，scope/route/hash/一次额度不变。
- **测试与实施。** 保存batch03真实初始A/repair/catalog原件及来源；先运行发布Schema不一致、多层错误聚合、容器要求删改、policy合法子项篡改的独立风险回归。已有后期/源动作/Voice/BGM/SFX/异步保护仍完整回归。前置Astra复核设计后才改生产；每一变体记录Expected/Actual，完整集成矩阵与项目检查后再冻结新软件。实时评测仍新批32Creation，历史FAIL不改。

这里对齐的是现有合同在模型入口的可表达范围与诊断/保护，不授权扩展Material canonical字段或改变required/Rights/Match/Readiness。若实施发现必须新增语义承载/新正式引用合同，停止该项另行设计与评审；不得靠隐藏缺口宣称全部解决。


前置Astra结论MODIFY已落实到本设计：不删除合法可选policy，不新增标量constraints键名白名单；A的queries是唯一查询入口，不能原样引用允许constraints查询对象的通用说明；不把intent.function自动判为后期。当前测试仅新增离线真实fixture和8个同矩阵风险变体，生产代码仍未修改；先取得现状失败证据。


### 13.7 A边界对齐软件完成（2026-10-07，真实新批尚未执行）

落实§13.6及Astra前置MODIFY：发布Schema保留可选字符串policy/普通标量constraints，限定既有模态例外及本轮来源引用；A queries为每条Need与constraints并列的唯一入口。语义主体/数量/禁令仍由Director写完整intent，不接收未知列表filter；后期归属仅明确责任，不自动删除Need或分类function。Voice Schema/消费者共用原范围常量，未变准入。

完整Draft Schema报错时，对结构已合法的Need执行独立来源和实际Domain/NeedCompiler检查；同Need来源错误不遮蔽可独立检查的filter错误。坏输入不会通过默认化生成Plan。repair保护合法policy子项、原未知dict/list约束，无法安全转换的容器只可拒绝；没有增加额度、放宽未知引用或自动搬移语义。原POLICY、合法Plan/Need身份/字段和旧冻结v3复算保持；旧pending字节不迁移、不恢复。

batch03原A/repair/catalog脱敏原件4份纳入原fixture目录；新增8个独立风险变体同矩阵。修前run-009 **3 PASS/5 FAIL**，生产/257现场不变；修后run-010 **8 PASS**。澄清queries层级后最终run-013 **80 PASS/0 FAIL/0 GAP/0未执行**，全量 **818 PASS/5既有skip**（62.31秒）、115技能/compileall/diff通过。覆盖历史多层错误、同Need来源/约束组合、列表删改拒绝、policy合法子项保护、发布Schema非法输入拒绝、合法policy/非空引用/Voice+BGM+SFX对照，原生异步A/B repair和全部旧基线仍通过。

Main只读加载旧63da编译器，与当前4类合法对照的完整Plan字段/ID相等；Astra另对image/video/Voice/BGM/SFX及Voice资产/consent、视觉偏好和continuity复核，Schema接受且Plan序列化逐字节相等，最终CONTINUE。模型入口Schema仍不能替代完整编译或独立语义验收，未知容器也不保证可repair。

257旧现场、原25fixture、batch02/03失败原件不变；新增4fixture后当前总29。此软件批新模型/Supply/Provider/生成/TTS/Build调用0，未恢复本批FAIL。生产SHA `79e580c163c77cafc47d4056c910e1aaf5bcc49419be31e78497d08588a54825`；后续固定commit、安全加载和batch04重新32个Creation，由唯一验收/当前状态具名补记。当前R4目标仍未完成，不认领Smoke。

### 13.8 batch04：结构通过，独立语义FAIL（2026-10-07，STOP）

§13.7软件固定commit `b819d2877c65d2c10836d076415a0cc47690377b` / source `79e580c163c77cafc47d4056c910e1aaf5bcc49419be31e78497d08588a54825`，完成既定安全加载/日志精确备份/实时空闲及套餐检查，再独立冻结32正常Creation。第0项正常Preparation/A/B0/Truth四原run全部ok/released，无repair，首次正式合同通过及原生持久重载一致，停在Supply import前。首个真实A的旧结构问题未重现；这不等于R4整体通过。

独立语义验收发现：冻结SCENES明确“在后期叠加正文”，B却把“由后期叠加。”及引用SCRIPT碎片列成视觉required。两张白纸/静态图/静音/冻结正文保留，但后期职责被送到素材硬审核。Astra STOP支持。primary_visual的postproduction符合当前合同，不列失败；无人脸/人物在Prep有来源，不称A凭空新增。自然光/干净桌面等可属Director构图，但同时进入preferred字段和description required，记为强度混合风险；失败不依赖争议项。

软件证明编号/原文覆盖/源绑定，并不证明模型分类正确。`visual_contract.classification_units`按标点切出被引号割开的正文碎片；B拥有完整Need/source/preference上下文，仍可给出Schema合法而关系错误的kind；`validate_compilation`接受完整合法kind时没有独立后期语义证据。Truth仅复核正文事实/创作表达，不承担Material分类证明。事实与推断分别保存，不将所有错误归咎信息缺失或制作模型能力。

**本批STOP：**1项语义FAIL、31未执行、held-out0/16；合同1/1执行项（1/32计划），语义0/1。墙钟257.450秒、Planning含Truth至切点173.171秒；4原提交、36assistant/32工具、21原请求观察，7callback含3缓存重入，实际重复提交0。Supply/Provider/生成/TTS/Build/repair/工程介入0。文字套餐5小时97→96%、周98→98%，账单未知。旧257正式现场/29fixture/batch02/03原件、固定版本/工具/样本/SCRIPT未变；独立评分不改正式产物。本Task的历史FAIL均保留。

**后续独立软件阶段的设计输入（本节不认领已实施）：**

1. 保留该真实A、B输入/分类/Plan/Requirements、正常确认/Preparation及Truth为事故fixture，并从原方案独立固定Expected。原文既不删除也不手工改成成功产物。
2. 先扩同一矩阵的关系风险：素材自身属性、图中禁止文字、引用正文、后期叠加义务、明确soft与hard强度分别核对；包含真实错误分类通过Schema的反例，不以self-consistency给自己出答案。
3. 源引用链核对到确认方案/Mode，不能只因上游模型文字冻结就当成新增硬限制授权；保留合法Director构图与可证明的源动作，不无差别收紧创作自由。
4. 统一评审完整语义单元/引号和否定关系、A硬软重复及B错误kind的停止路径。简单加关键词/把全部正文片段统一改postproduction/默认required/增加repair额度均不作为默认方案。产品期望无法确定时明确CONTRACT_GAP，不能改基线假装修好。
5. 涉及单元政策、跨阶段语义合同或缓存身份变更先Astra设计复核；离线真实内部集成先证明原事故与反向保护，再整体不回归。保持Material V1.3 canonical及Creator/Director/Truth/Hypit职责，不顺手加入Provider/Matcher/新框架或第二状态机。
6. 软件通过后新固定版本/安全加载/独立新批R4，仍用完整32项门槛；本批不得重计成功。当前停止真实模型，Smoke/E2E后置。

[独立语义评分](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch04-independent-semantic-review.json)、[结构化运行](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch04-actual-run-summary.json)、[Astra STOP](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch04-astra-review.txt)。

### 13.9 独立语义关系修正设计（2026-10-07，实施前）

以§13.8真实事故为输入，当前仅保存13份原件/来源/独立预期，不改生产。本设计仍采用§11两阶段，不把自由语义改造成由分类原子重建整个Plan，不增加独立生产模型Gate或请求。模型继续负责语义；程序收回可确定的语法边界、同一确认依据的传递、版本与身份。

**修改范围和可证实出口：**

1. **完整引用边界。** 为新产品编译政策增加一个无损、引号/括号感知的单元切分策略：仍以原标点分边，配对引用或括号内部标点不截断；保留所有空白、Unicode、字符位置及原字节，单元并列顺序不变。英语单词中的apostrophe不视为引号。只做语法关系，不看“后期/叠加/字幕”等关键词，更不据此选择kind。未闭合或错误嵌套的明确配对语法拒绝派发B，不默认required。引用只保护完整性，不把整个含否定/后期的段落一律postproduction。40单元及容量限额不扩大，不删除需求来满足限额。
2. **同一确认语义依据。** 新B实际请求提供程序拥有且已冻结的SCRIPT/SCENES/TREATMENT原件，与完整Need、source、Mode及偏好引用一同进入确定批次摘要。不是模型返回另一份正文，也不依赖其他会话或从自然语言中的路径读取。验证与重入使用同一冻结依据；不把A/Preparation自行写出的限制自动当成Creator授权。
3. **语义任务明确到审核对象。** A明确区分原素材可观察条件、显式创作软偏好和后期工作，后期计划继续留在确认SCENES/TREATMENT；只有原素材本身必须包含的字/图案才保留为素材条件，不禁止合法的印刷字、屏幕内容或动态源动作。B明确required审的是原素材可观察性，引用正文内容不自动成为背景图硬条件；“图中不含字”与“后期叠加字”分别处理。显式soft与description重复表达须沿偏好来源判断，确实混合且无法无损区分时unresolved，不默认required；叙事function仍按语义判断，非全部默认后期。已有共享一次repair不加额。
4. **版本及原件。** 新产品采用新的内部编译政策（拟`semantic-planning-compiler@2` / 引用单元策略@8）；既有@1有效v3冻结记录按原身份、原切分政策加载，@1/@2未知/冲突拒绝，不通过更改旧checkpoint或重编译修复历史。新政策参与Plan/Need identity、snapshot/batch和请求身份，修复额度不重置。既有standalone Material分类/缓存保持@7行为；canonical MaterialNeed@1、Requirements、V1.3及Material观察/Gate不改。旧pending只允许原身份对账，不套用新message重新提交。
5. **先证据后生产。** 同一矩阵新增真实引用回放、嵌套Unicode/括号、apostrophe合法对照、明确未闭合引用、source action/soft/postproduction对照、旧政策加载、新政策错误复用及原生持久链。Expected由独立原件/oracle固定，不由被测切分器生成；优先扩现有连续集成。先运行现状记录FAIL，再Astra前置复核、最小实施，完整不回归后才能固定下一软件版本。

**保留的语义边界：** 此修正可证明引用不破碎、确认依据真实传递、身份及完整覆盖可靠；不能声称程序已理解任意自然语言，不能声称合法kind必然正确。历史B错误kind的离线回放应明确区分结构PASS与独立语义FAIL；仅引号切分变化让旧ID不适用不能被包装成“已修复所有语义错误”。生产仍不添加一个模型自称覆盖就放行的Gate，真实独立32项R4继续承担语义发布验收。若Astra核查认为还需新语义承载/职责合同，先记录缺口，不用字词黑白名单或修改oracle掩盖。

上述为Main提出的最小方案，尚待Astra前置设计复核；本批不启动服务/模型/Supply，也不恢复batch04。

Astra前置MODIFY已落实（§13.9补充）：程序固定映射`compiler@1→units@7`、`compiler@2→units@8`，未知或冲突拒绝；政策参数贯穿身份/批次/bind/repair/verify，不依赖全局默认复算旧记录。旧有效@1的只读复算/复制保留原件；旧pending只对账不重新派发。原始B unit响应与compiled canonical缓存区分：前者由政策/冻结文本/units/request隔离，后者沿既有缓存键且新Need身份使其不可误复用旧输入。每Need包括显式preference的40项上限及完整确认上下文单批容量同时保留。

切分语法限定：支持`「」/『』/“”/‘’/ASCII双引号`与`()/（）/[]/【】/{}`的配对/嵌套；引号内容中括号作为字面内容，括号内可以包含引号；奇数反斜线转义的引号保留为字面内容。ASCII单引号不做分组，英语apostrophe/所有格不误判；curly apostrophe在词中为普通字符，数字后无配对开启的双引号/右弯引号为尺寸符号。没有已开启配对的独立右括号可作为列表编号普通文本；明确开启而未闭合或错嵌套拒绝，不补字。支持范围写入实际新B说明，不声称识别所有自然语言语法。

验收三类证据独立：旧@1实际事故仍结构PASS/语义FAIL；新@2相同文本引用完整、字节覆盖无损、真实canonical进入B并可稳定重入；新ID/新形状的故意错误kind仍可结构PASS但必须独立语义FAIL。正确kind离线fixture只证可表达正确合同，不认领真实模型改善。实际SEMANTIC_CHECKPOINT原件追加后此事故fixture共14份。以上修订后Astra允许实施；先跑固定现状失败测试，再改生产。

### 13.10 引用关系软件修正完成（2026-10-07，真实新批未执行）

按§13.9及Astra前置MODIFY实施compiler@2/units@8：无损配对语法切分、实际冻结三文件与完整上下文进入B及批次摘要，明确原素材/软偏好/引用正文/后期职责。@1→@7在旧身份、bind、verify及副本显式穿透；未知/冲突政策拒绝，旧pending不重发。新政策隔离Plan/Need/请求身份，standalone及compiled canonical cache仍沿原@7合同；共享repair额度不增加，Material V1.3未改。

先保留修前run-014测试缺陷与生产FAIL，纠正测试读取方式后run-015为2 PASS/4 FAIL。修后局部run-016/017通过，但完整run-018为87 PASS/1 FAIL：副本持久化在SCENES落盘前读取文件。没有改期望或跳过；persist核验实际待写入三文件、load核验已做manifest摘要检查的三文件后，完整run-019为**88 PASS/0 FAIL/0 GAP/0未执行**。全量**826 PASS/5既有skip**（59.06秒）、115技能/compileall/diff通过，Astra最终CONTINUE。run-018原FAIL永久保留。

三类证据分别保留：真实旧B仍结构PASS/独立语义FAIL；新unit引用完整且真实canonical进入原生A/B→Truth→persist/load/reentry；新ID/新形状的错误kind仍结构PASS但独立语义FAIL。正确kind替身仅证明合同可表达，不认领真实模型改善或普遍语义理解。257旧现场、原29fixture保持；新增14原件/独立预期后43fixture前后不变。软件新模型/Supply/Provider/生成/TTS/Build调用0，未修改正式历史产物或评分。

生产SHA `0657a8c27e3cf6ef2ace05ed8a8c00c15cb7604ff28dcd1d3ac28863e7fcfa48`，软件JUnit/Astra/原件指纹保存受保护batch05预提交目录。下一步仅提交本软件范围、实时空闲/套餐预检、实际raw-stream精确备份及安全加载，再用原16主题/oracle建立32个全新Creation独立R4。batch04及所有旧FAIL不恢复、不倒算；Smoke=NO。固定commit/服务与真实成绩另记唯一验收。

### 13.11 batch05：引用改善，但叙事义务仍错误进入required（2026-10-07，FAIL / STOP）

固定§13.10的软件commit `59bd7d857c6d955761a0d7fc217c713477b02762` / source `0657a8c27e3cf6ef2ace05ed8a8c00c15cb7604ff28dcd1d3ac28863e7fcfa48`，安全加载/完整实际日志备份、实时空闲和套餐授权检查后，新建32正常确认Creation。第0项 `cr_d5f751bb08874761ade57d08563da9dc` / `fa_2bf0f2ae21664119ddd7ec17145e6ed6` 正常Preparation、A、B0、Truth四run全部ok/released，无repair；正式合同/持久重载通过，停在原生Supply import前。引用正文完整且正文/后期叠加/不为此制造额外Need等均正确postproduction，前次故障确有改善，但不能因此算语义PASS。

独立语义FAIL及Astra STOP：正式required“不要替读者补完两张纸的来由。”属于作者叙事/事实边界。它有content-core/Truth及Director来源，不是凭空新增；**同一素材不变，仅作者叙事改变即可违反**，原图片自身不能核验。应现有叙事用途/postproduction承载，无法确定则unresolved。No people/no printed text有本次上游硬来源，preferred字段重复不足以单独证明升级；失败不依赖这项。两张白纸required/image/9:16/silent/SCRIPT均保留，明确required语义1/1不能抵消额外错误审核目标。Truth只证明正文，不证明素材kind。

本批立即STOP，**1项语义FAIL/31未执行**，held-out0/16；初始及最终正式合同1/1执行项（1/32计划），独立语义0/1。墙钟277.094秒、Planning含Truth至切点193.519秒；4原提交、33assistant/41工具、23原请求pending观察，7应用callback含3缓存原请求重入，重复实际提交0。NORMALIZE/repair/report repair/补证/工程介入0；Supply/Provider/生成/TTS/Build0，state violations0。套餐5小时96→95%、周98→98%，是共享账号比例，实际账单未知。

257旧正式现场、43fixture、4旧批全部原文件（原批120、02批135、03批137、04批147）、source/tool/HEAD/samples/SCRIPT均未变。所有批无pending/submitting/runtime-release待办，Gateway active/lost/audit0。评分只更新诊断记录，正式Plan/Requirements/Truth完整hash保持，完整原日志/脱敏会话/请求/时间/来源/独立反事实评分保存受保护batch05目录。旧FAIL不恢复、不倒算，不启动后31项或Smoke。

后续独立治理输入：把此实际A/B/正式clauses/冻结来源保留为fixture，与“画面不出现可识别公司文字”等真正素材可观察条件作关系对照；先固定Expected/Actual和软件风险分布。对同一素材保持而改变叙事的反事实，说明分类审核对象而非词面，禁止按“不要/来由”等关键词或全function默认处理。不追加修复额度，不把正确替身kind当真实模型改善；经必要设计复核、完整离线回归、另固定版本及安全加载后，才另起完整32项R4。此处不授权手工救场或放宽原门槛。

[完整结构化记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch05-actual-run-summary.json)、[独立语义评分](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch05-independent-semantic-review.json)、[Astra STOP](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch05-astra-review.txt)。R4整体目标未达成，READY_FOR_MATERIAL_SMOKE=NO。

### 13.12 审核对象关系对齐设计（2026-10-07，独立软件阶段）

batch05正式原件/实际B请求/真实冻结来源14份及独立Expected/来源2份（共16）保存为事故fixture；旧FAIL不改。当前生产仍59bd7d85，只改测试/文档先固定Expected/Actual。此项保留§11 A/B两阶段及既有四kind，不引入模型复核Gate、第三次调用、自由rationale、第二状态机或新Domain字段。

**根因及范围：** 当前B把“必要主体/数量/禁令保持required”列在审核对象规则之前；“禁令”包括素材可观察禁令及作者叙事/事实禁令，有来源不代表可由素材满足。拟将“先确定对象→再确定是否硬要求→最后选择kind”作为程序拥有、版本化的分类任务说明（`material-review-target@1`）。模型继续理解语义并返回原id/kind/preference_source，程序不按关键词推断kind，也不把错误Schema合法响应自动改为成功。

- A的现有intent.description描述原素材可观察性；作者叙事/事实义务由已有confirmed/handoff/Truth及叙事function保留，不复制成采购条件，不丢弃创作要求。动态动作若要求原视频实际发生，仍保留原素材条件，不按function字段默认后期。软偏好沿已有preferred字段。
- B先判断原素材观察能否核验。对候选required运用反事实：同一素材字节不变、只改作者叙述或后期行为就可违反的义务，不是素材required；按既有postproduction职责承载，无法确定则unresolved。反事实仅说明required审核对象，不将所有观众效果、偏好或未知表达统一改后期。真正可见公司文字/主体数量/源动作禁令保持，明确软偏好不升级。提供对象不同但形式相似的成对示例，不按“不要/来由”等词或字段名分类。
- 程序固定的review_target说明随新A/B输入及新B批次摘要提供；不接受模型编辑/返回另一个说明。新compiler政策@3映射units@8，review_target参与有效输入/批次/请求身份。有效旧@1→@7、@2→@8按原算法/原字节加载与复制；旧pending先原身份对账，不重新提交新说明或刷新额度。@2的完整canonical/batches校验不因POLICY默认升至@3而弱化。standalone/Material缓存算法、canonical Requirements、V1.3及Truth职责不变。
- 同一矩阵增加真实旧结果结构PASS/独立语义FAIL、正反关系对照、实际原生A/B请求目标说明传递、旧@2恢复/副本、政策/批次身份和B repair原目标保持。Expected固定于原proposal/oracle及人工反事实，不由被测分类器生成。正确外部响应替身只证内部合同能表达与无回归；不证明模型会作正确语义判断。

先运行现状并保留PASS/FAIL；Astra前置关键复核后最小实施，再完整回归。软件通过只允许另固定版本/安全加载/完整新32项R4，batch05仍停止，留出门槛不改。若复核认为必须新增语义承载或变更冻结职责，先记录具体依赖，不通过新字段或Gate掩盖。

Astra前置CONTINUE已落实：审核对象反事实仅用于视觉内容条款，不替代Rights/授权/来源真实性/技术准入；明确@1/@2/@3能力分派而非默认POLICY误降级。新A/B及共享A/B修复同用程序固定说明，B完整批次摘要绑定该说明，旧@2批次不注入新字段。保留新政策下结构合法错误kind的独立FAIL反例，不能将说明传递或替身正确分类当真实改善。现状run-020保留测试期望漏显式暖光偏好及生产FAIL；只纠正这项测试后run-021为3 PASS/4 FAIL，生产/257现场/59fixture不变，再修改生产。

### 13.13 审核对象说明软件回归完成（2026-10-07，真实新批未执行）

按§13.12前置CONTINUE最小实施：新@3→units@8加入程序固定review_target，先审核对象再强度/kind；A不把作者义务复制为asset条件，B解释同素材/不同叙事反事实及成对可观察禁令，Rights/授权/来源真实性/技术准入原合同明确保持。说明进入实际A/B和共享A/B repair，新B批次摘要包含说明；没有模型rationale、新调用、新kind、第二Gate或修复额度。有效@2的canonical/batches校验显式保留，旧批次不注入新说明，@1及standalone不变，旧pending不派发/不改记录。

修前run-021 **3 PASS/4 FAIL**，修后局部run-022 **7 PASS**；再补独立A repair目标和新政策错误kind反例后完整run-023 **96 PASS/0 FAIL/0 GAP/0未执行**。全量**834 PASS/5既有skip**（61.09秒）、115技能/compileall/diff通过。旧@2真实checkpoint/Plan及副本精确复算、SCENES改字及batches摘要坏拒绝；正反条件分别保留素材公司文字禁令required、作者经历禁令post、function原视频源动作required。原生A/B→Truth→persist/load/reentry以及A/B共享一次repair说明不漂移。

保留旧@2与新@3相同错误kind的结构PASS/独立语义FAIL；正确外部fixture仅证正式合同可表达，不算模型语义成绩。257旧正式现场和原43fixture未改；新增16原件/Expected/来源后59fixture前后保持，全部5旧批原件hash保留。软件真实模型/Provider/Supply/生成/TTS/Build调用0，batch05 FAIL不恢复、不倒算，当前Smoke=NO。

生产SHA `f01fe3317b4aa223caddea08ee0ee86cf5d3347944dc9698fd997c7a00e66005`；软件JUnit/源码及旧现场hash保存在受保护batch06预提交目录。当前等待实际diff的Astra最终冻结结论；只有CONTINUE与完整对账成立才提交、实际raw-stream精确备份安全加载，并另起完整32项R4。固定commit/加载及真实成绩由唯一验收另记。

Astra实际diff最终CONTINUE（run023及834全量检查完成后）：无新增必要修订；源/工具/257旧现场/59fixture对账一致可固定新commit、安全加载，随后新32项R4逐项独立语义核定。新说明传递不等于真实模型通过，旧batch05 FAIL及所有历史FAIL不改，Smoke仍未放行。

§13.13软件已固定commit0b176a2a8fa30b01c652aa044f176feb93c2639e，source f01fe3317b4aa223caddea08ee0ee86cf5d3347944dc9698fd997c7a00e66005。实际日志停服精确备份后12:19:50安全加载Web/Gateway，空闲及原件对账PASS；新batch06冻结原16主题的32独立正常Creation，开始第0项，尚无真实成绩。具体加载记录由唯一验收保留，不覆盖batch05 FAIL，不启动Smoke。

### 13.14 batch06：素材属性与后期用途混合分类仍语义FAIL（2026-10-07，STOP）

固定0b176a2a/sourcef01fe331，以32个全新正常Creation执行第0项。Preparation/A/一次共享A repair/B0/Truth五原run全部ok/released；初始一个query超过100字符，既有Schema已明确maxLength100，系统仅修查询且有效语义不变，不存在查询长度Schema缺口。正式合同/Truth及持久重载PASS，原生Supply import前停止。

独立Main审核与Astra STOP：“整体构图留出较充足的负空间以便后期叠加一行文字;”被整句编为postproduction。源图构图是素材可观察属性，“以便后期叠加”是用途修饰，不能将前者整体变成编辑操作。本次显式preferred_visual_details另有generous negative space around the two sheets，且无确认/Preparation硬负空间来源，因此应沿该来源为preference；确实无法无损判断则unresolved。明确负空间偏好已保留，不能报告遗漏、required降级或升级；但另处正确preference不能抵消错误kind。前次作者经历义务本次正确postproduction，证明改善而非整个语义通过。

原两张白纸required/image/9:16/silent/SCRIPT保留。本批1项语义FAIL、31未执行、held-out0/16；初始无需repair合同0/1，最终正式合同1/1执行项（1/32计划），独立语义0/1。墙钟211.901秒、Planning含Truth150.381秒；5原提交/36assistant/34工具/17原请求pending观察，9应用callback含4缓存原请求重入，重复提交0。NORMALIZE/report repair/补证/实际Supply/Provider/生成/TTS/Build/状态越界/工程介入0。共享套餐5小时95→94%、周98→98%，实际账单未知。

评分仅诊断，不修改正式Plan/Requirements/Truth；固定HEAD/source/tool/sample/SCRIPT、257旧正式现场/59fixture和全部5旧批原件SHA保持。五原run全部释放，各批pending/submitting/release待办0，Gatewayactive/lost/audit0。完整原始日志与脱敏会话、请求身份、原件/独立反事实评分和固定版本保存受保护batch06目录。本批FAIL/STOP永久保留，不追加repair、不启动后31项、不恢复计分，Smoke=NO。

后续独立治理先区分素材属性主谓与制作目的/用途修饰，并同时保护纯后期操作、作者义务、明确hard/soft来源及源视频动作；不按“后期/负空间”等关键词决定kind，不增加修复额度或生产语义Gate。新设计须保留@1/@2/@3原输入及缓存身份，前置Astra复核、实际失败回放和完整不回归后才能固定另一版本、新32项R4；本节不认领修复或模型通过。

[完整指标](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch06-actual-run-summary.json)、[独立评分](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch06-independent-semantic-review.json)、[Astra STOP](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch06-astra-review.txt)。

### 13.15 主体条件与用途关系治理设计（2026-10-07，实施前）

batch06保持FAIL/STOP，真实原件16份及独立Expected/来源2份归档为fixture，不改正式产物或评分。当前只设计和固定离线期望，不运行新模型。

本项明确软件与模型的不同责任：程序可证明完整原文、版本、身份及显式来源绑定，无法凭Schema证明自然语言kind正确。继续保留独立语义发布验收；不以替身返回正确kind认领语义可靠性。问题不是查询Schema缺项（已有100字符上限），也不是负空间偏好遗漏，而是B把用途修饰当成整句审核对象。

拟保持A/B两阶段及四kind，更新程序固定的审核任务为`material-review-target@2`、compiler@4/units@8：

1. A将原素材条件及明确soft来源写在已有字段，制作目的/作者叙事由function及冻结SCENES/TREATMENT保留。描述源属性时不得因附带制作用途而改变其职责；不能借此删除必要主体、动作、禁止条件或创作边界。
2. B对所有候选kind先辨识完整语义单元的主谓条件和目的/用途修饰，再确定审核对象与hard/soft。postproduction只适用于叙事义务、编辑动作或表达用途本身；源属性附带“为了某种后期用途”仍沿源属性来源处理。明确soft属性沿所属Need的既有preference_source，真实hard源主体/数量/源动作仍required。并列且不可无损分类的不同职责返回unresolved，不用截字或猜测让整个单元通过。
3. 成对关系不限于事故词面：冷色源图用于疏离表达是软源属性；原图必须两张纸用于旁边叠字是必要源属性；实际后期叠字是编辑动作；原视频杯子落下用于慢放仍是源动作；作者经历义务仍由叙事/Truth承载。无新增模型输出字段/rationale、第三Gate、调用或repair额度。
4. 固定映射显式保留compiler@1→units@7、@2→units@8无review_target、@3→原review_target@1、@4→review_target@2。旧@3真实checkpoint及批次digest按原说明精确复算，不因更新全局常量污染旧输入；旧pending只按原身份核对、不派发新请求或刷新额度。新说明参与有效A/B/repair输入、批次及Plan/Need/request身份。
5. 先运行同一矩阵：真实旧wrong-kind及新政策同形wrong-kind仍结构PASS/独立语义FAIL；关系成对正确对照；实际A/B和共享repair传递同一任务；旧@3完整持久恢复/复制、坏canonical/digest拒绝；新旧身份隔离。沿用已有完整异步Owner/Truth/Supply切点组合，不复制另一执行器或保护性测试集。

前置Astra复核后才最小实施，完整不回归、固定新版本/安全加载后才另起原16主题的32独立R4。该修正只能证明任务定义与控制面无回归，模型语义改善须由新真实评测证明；所有旧FAIL和原门槛不变，Smoke未放行。

Astra前置CONTINUE：关系解释不能实现为词序/关键词；补用途前置软属性与后期裁切形成留白对照。新target@2实际携带关系规则，@3原target@1固定完整保存，不从新对象删字段模拟。独立编辑义务不可整体跟随源属性，无法无损分类仍unresolved。修前默认目录run-018保留2PASS/5FAIL，其中旧批次比较遗漏JSON整数key编码为测试缺陷；只修测试比较为规范JSON，后续恢复同一r4-preflight输出入口，生产不变。

修前r4-preflight/run-024为3PASS/4FAIL，生产sourcef01不变；修后run-025为13PASS/2FAIL，外部正确对照误将真实Mode的preference id=1硬编码到隔离Mode（只有id=0），属于测试缺陷。仅从实际B请求的明确原preference文本取得程序id，未修改原件或生产宽限，完整run-026为103PASS/0FAIL/0GAP/0未执行，257旧现场/77fixture不变。既有native默认版本期望随正式@4更新，旧@3独立原件/批次精确复算保留。

### 13.16 主体条件与用途关系软件验收完成（2026-10-07，未执行新真实模型）

按§13.15及Astra前置CONTINUE完成compiler@4/target@2：实际任务携带主谓/用途、审核对象、强度/kind关系规则，A/B及共享repair一致使用。旧@3完整原target@1独立保存，原真实B payload/digest/checkpoint/复制精确恢复；@1/@2及standalone不变，旧pending不新派发或刷新额度。源属性不因用途整体变后期，独立混合义务无法无损分类仍unresolved，无词面算法、新模型Gate/输出字段/调用/额度，Material V1.3职责保持。

用途前置软源属性、明确hard主体＋用途、纯后期叠字、后期裁切留白、源动作＋用途及作者事实义务对照均通过正式内部编译。真实旧和新政策错误kind仍结构PASS/独立语义FAIL，正确替身仅证明合同可表达，不认领真实模型改善。

最终同一入口run-027 **103 PASS/0 FAIL/0 GAP/0未执行**，全量 **841 PASS/5既有skip**（60.44秒）、115技能/compileall/diff通过，Astra实际diffCONTINUE，无新增必要修订。首个全量834PASS/5skip/1ERROR因新增helper遗漏parametrize，原JUnit保留，仅补测试参数化后完整重跑；run018/024/025及测试缺陷不删除。257旧正式现场/原59fixture未改，新增18后77fixture前后保持，六旧批完整原件保存。生产SHA `71e5ecbbafdfd7104b835a5b6b2a3071a2132e291d31d5134dab9281547e99e4`，软件真实调用及Supply下游0。

软件冻结条件成立，后续仅按已授权范围窄提交、本轮实际日志停服精确备份、安全加载/实时空闲/套餐预检后，用原16主题及独立oracle另建32个全新正常Creation进行R4；旧batch06及全部历史FAIL不恢复不倒算。软件通过不放行Smoke，真实成绩另记唯一验收。

§13.16后续 batch07 固定版本及安全加载（2026-10-07，真实结果未定）

§13.15/13.16软件固定commit7685953c72925b195aa7e882996aca076a2151bb / source71e5ecbbafdfd7104b835a5b6b2a3071a2132e291d31d5134dab9281547e99e4，仅22获批软件/fixture/Task文件，凭证/运行产物0、无push，用户其余工作树保留。run027103矩阵PASS、841全量PASS/5既有skip、115技能/compileall/diff及AstraCONTINUE。

实时8旧Owner有效操作0，unknown/pending/submitting/release待办0，Gatewayactive/lost/audit0；同Key文字套餐94%/98%，无fallback，实际账单未知。257旧正式现场/77fixture及全部六旧批原件SHA一致。实际raw-stream停服后精确备份172336字节、SHA2047330750c5f7c2bfe05910d0aec41c4f6906422aaddd8db8c22f8a95b2b773核验，12:57:24 Web/Gateway新PID99217/99215安全加载，HTTP200/Gateway空闲；无进程内SHA端点，依据为新PID/时间/执行文件/cwd及固定源。

原16主题及独立oracle保持，新32正常确认Creation冻结隔离，请求身份独立，首次真实Prep/A/B/Truth开始；尚无新成绩。每项正式合同与独立语义均PASS才继续；禁止实际Supply/Provider/生成/TTS/Build，所有旧FAIL不恢复不倒算，Smoke=NO。[加载证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch07-release-loaded.json)。

### 13.17 batch07：前两项双PASS，第3项分类枚举与repair输出结构FAIL（2026-10-07，STOP）

固定7685953c/source71e5ecbb的新32项：第0/1项《桌上的两张纸》正式合同与独立语义均PASS，无repair，正式原件未改；第1项四相同scope Need的冗余风险保留，V1.3可一Asset多Need，不能事后加“一Need”评分。第2项《给绿植留一点时间》正常Prep/A/B0/唯一B repair四原runok/released，但正式消费者拒绝，Truth未执行；全部立即STOP，后29未执行、held-out0/16。

初始B unit8.kind为`narrative_or_postproduction`，复制了review_target的说明标签，合法四kind不包含该值。程序已拥有正确原文映射，却把非法kind与引用越界合并报“要求引用不属于冻结原文”，repair随后推理不存在的引用问题。实际初B只有required JSON例子；repair response_schema只是“same schema/IDs as original batch”说明字符串。真实repair返回batch_id/compiler_policy/review_target/responses/notes输入式wrapper且保留非法kind，_merge_repaired严格拒绝；不自动映射标签、不剥wrapper或再修。Astra STOP：MODEL_OUTPUT违规＋STRUCTURAL_CONTRACT输出指导/错误诊断缺口，严格拒绝本身正确；误诊干扰修复有支持证据但不认领唯一因果。

3项已执行/29未执行，初始及最终正式合同2/3（计划2/32）；仅两项可正式语义评分，均PASS，失败项无正式Requirements，语义覆盖UNVERIFIED。共享repair1、正式成功0/1、NORMALIZE/report repair0。完成项累计墙钟616.810秒、Planning含Truth/失败边界401.139秒；失败项228.669秒。12实际提交/77assistant/104工具/51原请求观察，21应用callback含9缓存重入，无重复实际提交。Supply/Provider/生成/TTS/Build/状态越界/工程介入0。共享文字套餐94→91%、周98→98%，实际账单UNKNOWN。

257旧正式现场/77fixture/六旧批完整原件及HEAD/source/tool/原16主题/SCRIPT保持。所有12原run释放，所有批无pending/submitting/release待办、Gatewayactive/lost/audit0；完整原日志/脱敏会话/请求身份/原A/B/repair/现场hash保存在batch07受保护根。评分不修改正式产物；失败项无正式Plan/Requirements/Truth，不虚构语义成绩。A的preferred描述夹连续源动作仅记录后续风险，不追加正式评分。本批及历史FAIL永久保留，Smoke=NO，不继续计分或恢复。

[完整指标](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch07-actual-run-summary.json)、[失败边界核定](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch07-independent-failed-review.json)、[Astra STOP](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch07-astra-review.txt)。

### 13.18 B分类输出合同与诊断最小后续方案（未实施）

本批保持FAIL/STOP，先把本次原A/B/repair实际请求、完整回复及冻结来源保存为独立事故fixture。维持A/B两阶段、现有四kind、一次持久repair及Material V1.3，不用更宽兼容救场。

1. 初始B与B repair使用程序统一构造的完整输出Schema，复用现有合法KINDS：精确字段、整数unit ID及顺序/覆盖、所属Need显式preference允许集合。元数据/语义任务标签不是输出枚举；不能回传输入对象。repair顶层仅batches，每项仅index/classifications，index由受影响批次决定，不让模型猜wrapper或扩批。
2. 程序在绑定原文前检查实际unit的kind类型/枚举与preference引用，分别报告非法kind、wrapper形状、ID覆盖、来源问题；所有严格拒绝保持。wrapper实际不符不能误报仅“覆盖”错误，非法kind不能误报冻结原文错误。新政策显式隔离有效输入/批次/请求身份，旧有效checkpoint精确复算、旧pending不重新提交/刷新额度。
3. 同一矩阵先真实失败回放固定Expected/Actual，证明初始错误定位及失败wrapper不能准入；原生异步集成的外部替身仅依据实际请求中的完整Schema与绝对输出路径交付正确单次repair，不从闭包补隐含输出合同。保留非法kind/坏wrapper/受影响多批次/已成功批次保护及所有旧合法路径。正确kind替身仍不算真实模型改善。
4. 跨阶段输入/内部政策变更先Astra设计复核，最小实施后完整矩阵和项目检查，再固定新版本、安全加载、原16主题完整新32项R4。不得沿本批第3项修写后续跑计分；Smoke与完整Material E2E仍后置。重复scope及A软硬混合仅作为独立诊断风险记录，本项不顺手扩为Domain重构或另加语义Gate。

### 13.19 B输出合同软件验收完成（2026-10-07，未执行新真实评测）

§13.18及Astra前置/实际diff CONTINUE后完成compiler@5：初始B与唯一B repair共用程序构造的Draft2020-12逐单元输出Schema，固定排序四kind、整数id及完整按序覆盖、所属Need的显式preference ID/null；repair精确affected indexes，顶层仅batches。运行时独立严格核验wrapper/ID/kind/pref，非法kind先报告unit.<id>.kind，不再误报冻结来源，错误wrapper与index分别报告。未放宽消费者、自动映射说明标签或剥wrapper，无新Gate/模型调用/额度/Domain重构。@4显式保留原target@2及无Schema批次digest，@1–3保持；旧pending不重派、不迁移。

新增batch07实际事故原件、请求与独立Expected，以及另存run00合法@4 checkpoint，共13fixture；失败项partial snapshot不冒充正式Plan。修前run028因测试误用Python严格反序列化7FAIL，原记录保留；仅改为JSON反序列化后run029 **2PASS/5FAIL**，准确暴露诊断/Schema/身份缺口，生产不变。修后完整run030110PASS；补唯一B repair显式Schema说明后最终run031 **110PASS/0FAIL/0GAP/0未执行**。全量 **848PASS/5既有skip**（62.79秒），115技能、compileall、diff PASS。既有原生异步Owner accepted/pending/原run释放/Truth/Supply前切点及多批保护执行，外部B/repair替身从实际提交Schema与绝对path获得形状/ID，只有固定语义答案；不认领真实模型改善。

生产SHA `b64681a0c8b650d509824e4cb376fc6dfb05d0c0fc6a5d3a8850a812f1f4e548`，257旧正式现场/90fixture保持；batch07及全部历史FAIL不改，软件外部模型/Supply下游0。Astra实际diff无需新增修订，软件冻结条件满足。下一步按既有授权窄提交、安全加载/套餐/实时空闲检查，在原16主题/oracle另建全新32项batch08；不能续跑或重计batch07，不放行Smoke。

§13.19后续 R4 batch08 固定版本与安全加载（2026-10-07，真实结果未定）

§13.18/13.19固定commit4614db7142ab6e189dde49fefd7356eafbb2cf74/sourceb64681a0c8b650d509824e4cb376fc6dfb05d0c0fc6a5d3a8850a812f1f4e548，仅17获批源码/测试/fixture/Task文件，凭证/运行产物0，无push，用户其余工作树保留。run031110矩阵PASS/848全量PASS/5既有skip、115技能/compileall/diff及AstraCONTINUE。

实时8旧Owner有效操作0，各批unknown/pending/submitting/release待办0，Gatewayactive/lost/audit0；同Key文字套餐91%/98%，无fallback，实际账单UNKNOWN。257旧正式现场/90fixture及全部七旧批原件SHA保持。实际raw-stream停服后精确备份1,150,865字节、SHAb3a4059cfdc3480a1386d4c7c49c940c99a33db82d076836c2504c8d9543639d核验，13:25:39 Web/Gateway新PID2814/2812安全加载，HTTP200/Gateway空闲。无进程内SHA端点，证据仍为新PID/时间/执行文件/cwd与固定源。

原16主题和独立oracle不变，冻结32全新独立正常确认Creation，真实成绩尚未产生；逐项实际Prep/A/B/Truth与独立语义评分，正式双PASS才继续。实际Supply/Provider/生成/TTS/Build禁止，全部历史FAIL保留，Smoke=NO。[加载记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch08-release-loaded.json)。

### 13.20 batch08：完整Schema实际生效，持续unresolved导致正式FAIL（2026-10-07，STOP）

固定4614db71/sourceb64681a0的新32项首项《桌上的两张纸》正常Preparation/A/B0/唯一B repair四原runok/released。初B与repair均通过实际完整输出Schema，四kind/wrapper/ID正常，repair与初B分类完全相同。unit5整个function为“Carries the entire 0–15 second visual in a single static frame; the two blank papers on the desk embody the unspoken subject, while the spoken line is layered on top in post-production by the SCENES / TREATMENT workflow.” 两次均unresolved，正式消费者正确拒绝；Truth未执行，无正式Plan/Requirements。

独立Main及Astra STOP本批/MODIFY后续定性：整段主要是成片使用、表达及后期操作，静态两张白纸已由description/image保留，整段postproduction为合理可表达对照。“严格拒绝unresolved正确”不等于“unresolved语义判断正确”。function强制整段确是实现事实，但本例不能证明它导致表达容量不足；不能只复制模型mixed理由作oracle，不能拆段后将时长使用或表达用途硬化。@5输出合同修复本次真实工作，仍不足以保证自然语言分类正确。

本批1项FAIL/31未执行、held-out0/16；初始输出Schema1/1合法，初始/最终可用正式合同0/1（计划0/32），repair0/1、无变化修复1；正式语义/required覆盖未验证。耗时218.823秒，失败Planning136.344秒；4原提交/25assistant/41工具/18原请求pending观察，7应用callback含3缓存原身份重入，无重复实际提交。Supply/Provider/生成/TTS/Build/状态越界/工程介入0。仅已购文字套餐91→90%、周98→98%，实际账单UNKNOWN。

源码/工具/原16主题/SCRIPT、257旧正式现场/90fixture及七旧批完整原件保持。四原run释放，各批pending/submitting/release待办0、Gatewayactive/lost/audit0，实际raw精确归档/脱敏会话/请求/原件SHA保存batch08受保护根。未修改正式产物、未追加repair、不继续或重计本批。全部历史FAIL保留，Smoke=NO。[指标](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch08-actual-run-summary.json)、[独立失败核定](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch08-independent-failed-review.json)、[Astra](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch08-astra-review.txt)。

### 13.21 成片使用与源素材条件语义任务补证方案（未实施）

基于§13.20及Astra修订，不默认修改function单元粒度。本次未证明软件容量缺陷，后续最小项仅明确分类任务的审核对象：对同一原素材保持不变、只修改时间线使用/叙事/排版即可违反的要求，应由成片职责承载；原素材内必须可观察的主体/数量/源动作/印刷文字/禁令仍沿来源required或明确preference。表达用途不因复述两纸/静态就变成新的采购义务，真正的源条件也不因位于function被默认postproduction。counterfactual是语义解释任务，不实现关键词或字段自动分类，不新增模型字段、Gate、调用或repair额度。

先保留实际A/B/repair与原确认/Preparation/Mode和独立Expected。实际unit5整段postproduction为合理对照，旧unresolved仍正式拒绝且历史FAIL不变。新增正反关系：相同静态图保持15秒/两纸象征犹豫/后期叠字均使用或表达；原视频必须杯子落下、原图必须两张纸、原印刷字须可见仍源素材条件；真正独立混合且不可无损单kind仍unresolved。不得仅因source约束重复便删除或自动放行，也不以固定替身正确标签认领模型改善。

若Astra前置复核接受，固定新的review_target@3与compiler@6→units@8，原@1–5完整说明、shape、Schema和digest显式保持，尤其@5完整output_schema必须继续存在，不能用“当前POLICY才带Schema”污染旧版本。新关系说明进入A/B/repair及身份；旧pending仅原身份对账，不重派/刷新额度。保留同一矩阵/原生异步/多批/版本保护，完整软件回归和实际diff复核后才新版本固定/安全加载、原16主题完整新32项；本方案不认领根治或放行Smoke。

### 13.22 成片使用与源条件软件验收完成（2026-10-07，未执行新真实评测）

§13.21经Astra前置和实际diff CONTINUE，compiler@6仍units@8，不修改function粒度。target@3新增审核对象反事实规则：只辅助判断义务约束谁，不按后期可编辑性分类；原图两纸条件在成片裁掉一张后仍约束原素材，使用方式/象征表达复述主体不自动创建或擦除源义务。A/B/共享repair一致收到新说明，无关键词/字段算法、额外字段/Gate/调用/repair额度，Material V1.3语义保持。

显式固定@4/@5原target@2及@5完整output_schema能力；@1–5原映射、批次身份和旧pending保护保持。batch08十份原件/独立Expected脱敏保存，partial snapshot不冒充正式Plan。实际unresolved在新旧政策都正式拒绝，整段postproduction仅独立合理对照，不恢复历史评分；12组源/使用/裁剪/源动作/印刷字/软偏好及真不可分混合保护通过。实际@5 B payload精确复算；合法@5checkpoint由真实内部模块离线派生并明确非真实历史PASS。

修前run0323PASS/2FAIL，暴露新任务传递/身份未实现，不是宣称已证实消费者故障；生产仍b646不变。修后同一完整run033 **115PASS/0FAIL/0GAP/0未执行**，全量 **853PASS/5既有skip**（63.20秒），115技能/compileall/diff PASS，Astra实际diff无必要修订。257旧正式现场/100fixture保持，软件实际模型及Supply下游0，source `aff2ed40dd85dbec74f9a8a894b1688626116e6b2de5b145d8e0443597f7ea53`。

软件证明任务说明/身份/合同传递，不证明模型语义改善，更不承诺根治。本次新真实证据须在另一固定版本及全新32项batch09中取得；旧batch08与全部历史FAIL保留、不倒算、不放行Smoke。按既有授权窄提交、安全加载/套餐/实时空闲检查后继续原16主题和原门槛。

§13.22后续 R4 batch09 固定版本与安全加载（2026-10-07，真实结果未定）

§13.21/13.22固定commit89bc154d228f443e784632cd74386c54d2558ab9/sourceaff2ed40dd85dbec74f9a8a894b1688626116e6b2de5b145d8e0443597f7ea53，仅14获批源码/测试/fixture/Task文件，凭证/运行产物0，无push，用户其余工作树保留。run033115矩阵PASS/853全量PASS/5既有skip、115技能/compileall/diff及AstraCONTINUE。

实时8旧Owner有效操作0，各批unknown/pending/submitting/release待办0，Gatewayactive/lost/audit0；同Key文字套餐90%/98%，无fallback，实际账单UNKNOWN。257旧正式现场/100fixture及全部八旧批原件SHA保持。实际raw-stream停服后精确备份130,268字节、SHA537989e82995f296b765a2674e19cae31e2f822275a00b37de39310e6706217f核验，13:41:53 Web/Gateway新PID4791/4789安全加载，HTTP200/Gateway空闲。无进程内SHA端点，证据为新PID/时间/执行文件/cwd与固定源。

原16主题和独立oracle不变，冻结32全新独立正常确认Creation，真实成绩尚未产生；逐项实际Prep/A/B/Truth与独立语义评分，正式双PASS才继续。实际Supply/Provider/生成/TTS/Build禁止，全部历史FAIL保留，Smoke=NO。[加载记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-release-loaded.json)。

### 13.23 batch09：正式合同PASS，屏幕/手部无来源硬化语义FAIL（2026-10-07，STOP）

固定89bc154d/sourceaff2的新32项首项《桌上的两张纸》，正常Prep/A/B0/Truth初次及一次Truth报告修复五原run全部ok/released。A/B正式合同无Planning repair；Truth初次误将创作短句作为supported_paraphrase，沿原有一次报告修复改为creative_expression/sources[]，正式Truth/Persist/Load及原生Supply前切点通过。

独立Main及Astra STOP：正式required“**不出现任何屏幕**”无冻结硬来源。确认稿和Preparation仅静态桌面两张白纸/15秒/9:16/silent/后期正文，Mode Visual Bible还列screens为日常素材；同Need明确soft preferred_visual_details包含no screens，不能以A自行写入description的禁令自证新增授权。禁止可识别手部也未查到冻结hard来源；禁止编造私人事实/画外人物不是禁止所有画内对象。纸空白有依据不计失败；全部实物印字/品牌包装/招牌存在部分Mode文字边界，不打包定罪，本次无需依赖范围争议即可FAIL。

本次15秒保持画面及整个function使用/叠字/作者来源义务正确postproduction；两张白纸/image/9:16/silent/SCRIPT和Mode风格/留白preference保持，说明改善而非整体语义通过。原required语义1/1保留，无遗漏/降级，但无来源hard至少2项使独立语义FAIL；正式合同/TruthPASSED不能抵消。评分不改正式产物、不降级救场。

本批1项语义FAIL/31未执行、held-out0/16。A/B初始无需Planning repair1/1；含Truth首次无报告修复0/1；最终正式合同1/1执行项（计划1/32），独立语义0/1。Planning repair0/N/A，Truth report repair1/1，NORMALIZE0。281.806秒、Planning含Truth219.945秒；5实际提交/30assistant/29工具/23原请求pending观察，9应用callback含4缓存原请求重入，重复实际提交0。两Truth请求共享同session、request hash与run独立，审计按一个实际transcript window计数一次，不把两run的同一会话重复累计。套餐90→89%/周98→98%，实际账单UNKNOWN。

Supply/Provider/生成/TTS/Build/状态越界/工程介入0。固定源/工具/原16主题/SCRIPT、257旧正式现场/100fixture及全部八旧批原件保持；五原run已释放，各批pending/submitting/release0，Gatewayactive/lost/audit0。正式原件SHA评分前后不变，raw精确归档/脱敏会话/完整请求/独立评分保存batch09受保护根。后31项不启动、历史FAIL不恢复不倒算，Smoke=NO。[完整指标](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-actual-run-summary.json)、[独立语义FAIL](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-independent-failed-review.json)、[Astra](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-astra-review.txt)。

后续不只增加相同语义提示。本例暴露A生成的描述被当成自身硬来源，而B的target/strength说明未能阻止无来源属性进入required。下一步先调查正式硬条款能否只由程序投影冻结Creator/Director原句、将模型创意描述/检索意图与硬来源分开；保留独立语义审核，不假装引用存在就证明含义正确。涉及新输入协议/责任边界须先单一Task设计及Astra前置复核，未完成离线证明前不另起真实批。

### 13.24 硬条款来源调查与设计约束（2026-10-07，调查中，未实施）

本节沿用当前R4 Goal及同一Task，不启动batch10、不修改batch09正式产物或成绩。实际源码仍89bc154d/sourceaff2；853 PASS/5既有skip是此前软件证据，不能认领本节方案已通过。2026-10-07 14:02核对Goal自09:35开始约4小时26分，活跃执行约4小时10分；此前“剩余2–3小时”仅适用于后续32项全部顺利的评测，不包含新增根因治理，现已失效。

**已证实的来源链缺口。** `semantic_planning._compile_need`将A的自由`intent.description/function`传入正式Need；`visual_contract.sources_for`再将它们作为需完整绑定的原文。程序证明的是“条款忠于A”，没有证明“A忠于确认要求”。B虽收到确认稿并有审核对象说明，仍将自行新增的屏幕/手部禁令标required。`constraints`中除查询、voice_delivery、required_source_kind、usage等既有例外之外的字段也进入来源候选；`NeedCompiler`还将多数标量constraints直接编译为检索filters。只改intent会留下跨字段入口。

**实际上游权威不能按冻结一刀切。**

| 输入 | 已有约束与证据 | 本次不得误认 |
| --- | --- | --- |
| 确认SCRIPT/SCENES/TREATMENT | 正常确认产生，Planning逐字节保护；SCENES含真实源条件与后期义务，TREATMENT含表达/声音 | 逐字存在不等于适用于原素材，也不等于required |
| Preparation Production Brief | `creation_preparation`已核对handoff中的brief及其冻结hash；本轮Planning context只有brief hash，没有brief正文 | 模型整理后被冻结，不自动获得新增Creator硬授权 |
| Creator Context / Truth | 含身份、隐私、事实与叙事边界，当前均为冻结快照 | 不编造人物事实不能变成禁止画面出现手部 |
| Creative Mode | `load_frozen_creative_mode`核验handoff；现有visual_material_style是软偏好，Director有镜头、素材与表达判断权 | Mode中的偏好、示例物件或表达说明不能批量硬化 |
| A语义草稿 | Director可规划合法新Need，但不获得新增身份、事实或预算；Task§11.3已明确 | 自己写一句禁令并不能自证为Creator要求；也不能因为没有逐字原句就误拒全部创意Need |

**前置复核结果：MODIFY。** Astra认可程序拥有上游来源目录、模型只选择已有ID的方向，但不认可“所有硬条件只能复制既有原句”作为直接实施方案。出处存在不能证明适用模态、强度或语义蕴含；Preparation不是新增授权入口；新创意Need不能静默删除或全部降软。复核要求先明确来源资格、完整消费者入口、合法Director具体化的承载及反向保护，再复核具体实现。

**下一软件批次的设计出口。** 在生产修改前，完成以下同一份合同方案与真实离线反例：

1. 程序目录逐项绑定实际原件、字段/范围、版本与上下文；模型不填path/hash/已授权标签。区分“证明出处”和“有资格施加该类约束”，不按来源文件或必须/不要关键词授予hard。
2. 明确上游义务、Director创意解法、软偏好及叙事/后期的承载；程序能投影的明确条件才由程序投影。没有原句的合法具体化不能由A自证授权，也不能一律拒绝或降软。该项仍待完成可实施定义，尚无合同变更通过结论。
3. 逐条核对intent、constraints、模态/时长/数量、默认值、检索过滤、生成输入和Match消费者。新增来源保护不得被其他字段绕过，也不得通过降低required来通过。
4. 同一矩阵固定batch09真实回放与反向预期：无来源禁屏/禁手与soft升级失败；用户明确禁屏、两纸数量、真实源动作保持；隐私叙事不转素材禁令；后期正文不转背景图文字；合法Director新Need保持；错误scene/模态、漏选与跨字段绕过不放行。原件回放仍记录历史FAIL，不用派生正例重计真实成功。
5. 新草稿/投影政策单独版本化，纳入请求/快照/批次身份；旧@1–6精确复算与pending原身份保持，未知不重派，不刷新repair。保留独立语义检查，不能以ID存在或引用完整宣称语义覆盖成立。

实现仍限定Planning应用层及必要的已有上下文传递；不改变Material V1.3 Domain、Rights、Match、Readiness或四方职责，不增加Gate、模型调用、状态机、公开路由或修复额度。上述未决合同解决、先失败证据与Astra前置复核通过后，才开始软件实现；软件验收后才另固定版本并重开32项真实Eval。当前Smoke=NO。

### 13.25 上游出处与B语义依据绑定的最小实施合同（候选，未实施）

采用§13.24复核后的选项一：不把所有hard强制投影为上游逐字原句，不删除合法创意Need，也不再只增加自然语言例子。A运输仍是一份语义草稿；B在同一次既有分类调用中，必须对正式条件给出程序可核验的上游依据绑定。引用存在只证明出处；语义适用、蕴含、强度及Director具体化仍是B的语义责任，并由独立Eval验收。这里不宣称程序能确定性消除所有无来源hard。

**修前证据。** 脱敏batch09保存14份逐字实际原件、原scope、独立Expected及来源SHA，共17文件，旧100fixture未改。同一矩阵新增第47行，run034实际1 PASS/2 FAIL：旧@6实际Plan/Requirements精确回放仍正式PASS、语义FAIL；当前B输出Schema没有依据字段；标量`constraints/screens=false`确实进入NeedCompiler硬filters，却不在分类单元中。后两项是本节新增保护未实现的FAIL，不冒充旧合同要求或被测模型语义已修复。生产sourceaff2、257旧现场及117fixture在该执行前后均保持。

**程序目录与资格。** 新应用层政策`semantic-planning-compiler@7`使用程序生成的`planning-authority-catalog@1`，与原scope/voice目录分开。条目包含程序ID、实际原件类别、字段/原文范围、原字节与摘要、适用scope、已知字段强度及可引用用途。确认SCENES、TREATMENT、经原handoff完整性验证的Mode文件、Creator/Truth和Preparation分别标来源；A只属于candidate，不进入上游目录。Preparation明标derived，不能单独支持新增Creator义务；隐私/事实字段不提供视觉物件禁令资格；既有Mode视觉风格明确soft，不可作为required依据。未知自由文本只作为待语义解释的上下文，不按文件名或必须/不要关键词授予hard。出处和上下文都进入固定请求及快照摘要，不让模型填path/hash/authority标签。

**A职责保持。** 继续规划Need、scope、模态、用途、importance和具体素材候选，允许服务既定表达目标的合法新增创意Need；不新增第二份正式合同，不让A再填写一套派生来源表。它不能自称用户新增硬授权、身份事实或预算；把自身自由描述放入草稿不等于已获准入。模型的自由检索短语和明确软偏好保持既有角色。初稿、修复与消费者使用同一A Schema。

**B运输合同。** 程序为每个视觉单元保留现有id/kind/preference_source，同时要求`basis`：

- `relation`为有限的`upstream_obligation / director_realization / preference / postproduction / unresolved`；`source_ids`为有界、唯一且实际目录中的ID，不返回路径、复制原文或“已授权”布尔值。
- required只允许前两种relation，必须引用实际可用于该目的且适用当前scope的上游依据；A候选、自身软字段、derived Preparation或隐私事实不能独立充当视觉hard来源。引用语义是否足够由B判断，程序不以ID存在断言充分。
- `director_realization`必须服务已接受目标且符合当前scope，不改变确认的对象/数量/源动作，不增加身份事实/授权/预算，不把既有soft或叙事边界改成素材禁令。“没有明显冲突”不是充分依据。合法新物件表达仍可存在；没有足够依据则unresolved，不删除或自动降软。
- preference沿既有显式偏好引用及已知soft强度；postproduction仍需按实际审核对象处理，不能吞掉真实源动作。无法确认对象、强度或依据则unresolved，沿原修复/拒绝流程，不产生新调用。

**完整视觉入口。** 除现有原文单元外，程序给本次B提供`review_type=control`的类型化候选控制单元，覆盖视觉Need的importance、duration_hint、desired_options、非查询constraints和模态参数。它们不能因不是字符串绕过检查。每个control的ID、path、值和已有消费者作用由程序生成；B同一次返回ACCEPT或UNRESOLVED及basis，不把控制项伪造为Material视觉原文条款。程序默认/已知派生值独立标明，只有与实际默认/冻结输入相符才能引用为operational依据。未知/不适用控制不进入filters、生成或Match，也不通过删字段救场。查询继续按G1处理；Voice身份/冻结SCRIPT/音色参数及Rights/授权/预算沿原确定性校验。纯声音B=0的既有合同保持，本节不新增音频模型审核；声音语义完整性继续由独立R4逐项证明，不能把此视觉来源修复扩大宣传为所有模态语义已确定性验证。

**编译、修复与恢复。** 所有视觉原文及control完整返回，结果先汇合，再验证当前目录/范围/强度/关系枚举及来源资格；不会因为basis存在直接推进。原文仍使用现有bind/validate，controls及依据只保存现有应用层checkpoint，不变更正式MaterialPlan/Requirements或另建权威sidecar。依据或control错误使用原单次共享repair，成功批次不改、不重派，未知按原run观察。@7目录/输入/单元/依据进入Plan身份、批次及checkpoint指纹；@1–6显式旧映射、原件复算和pending身份保持，禁止用缺少新证据降级绕过@7。

**实施前必须补齐并由Astra核对的细节。** 目录条目资格依据要落到实际字段/producer；Mode文档和Preparation读取必须复用handoff验证，不接受模型传入的替代原件；control的操作默认、创意选择和硬条件不能混同；现有单元/消息容量及完整覆盖上限不得靠截断或删项通过。新增运输Schema精确投影所有实际ID、关系/引用资格和control输出形状，初B与B repair相同约束。先增加独立正反对照及真实内部连续链，再实施生产；当前本节仍是候选合同，尚无@7实现或Astra通过结论。

验收必须包括：batch09无来源禁屏/禁手不能自证；用户明确禁屏、两纸数量、视频连续动作保留；合法Director新物件Need不误拒；隐私/事实/soft/derived Preparation不能充当硬授权；错误scene/模态、未知/重复/遗漏来源、缺basis及scalar/filter绕过拒绝；旧@6真实原件精确恢复与新身份不认领旧缓存；pending不重派、额度不刷新；原生确认→Preparation→A/B→Truth→persist/load→Supply前切点及全部不回归。固定正确外部回复只证明软件合同，错误但Schema合法的语义仍应在独立Expected中FAIL，不包装成软件可自动判定所有含义。

#### 13.25.1 实施前复核MODIFY的合同闭合

以下补充落实Astra的六项最小修订，仍需复核后才改生产。

**来源资格是引用用途，不是hard认证。** 目录按程序实际字段建立：

| 原件/字段类别 | 可作主要依据的relation | 已知限制 |
| --- | --- | --- |
| 确认SCENES正文 | upstream_obligation、director_realization、preference、postproduction | 行/单元绑定真实scene/segment/event；B仍判断对象、强度和蕴含，整行不自动hard |
| 确认TREATMENT的表达与声音原件 | 同上 | 全局表达可支持具体化；声音不能错绑视觉，叙事禁令不是像素禁令，均由B语义判断 |
| 确认SCRIPT | 非独立上下文依据、postproduction | 单独SCRIPT不能支持背景素材必须含字；有明确SCENES/TREATMENT印刷/屏幕要求时可作为被引用正文，与该主要依据共同引用 |
| 经验证video_plan.specs的duration/aspect/audio/language | upstream_obligation，限对应技术/音轨控制 | 用已有validate_video_plan及其SHA核验，canonical三文件必须一致；不能从15秒总片长直接证明静态源图有15秒素材时长 |
| Mode JSON的visual_material_style和现有明确软字段 | preference | 不提供hard或身份/预算依据；程序实际应用该默认另留操作记录 |
| 冻结Mode directing文档、表达目标 | director_realization、preference、postproduction；明确政策可待解释为upstream_obligation | 原条目保留完整上下文；示例物件不自动必需；JSON runtime/身份边界不成为视觉条件资格 |
| Creator身份/隐私/Voice、Truth事实/叙事、Content Core | postproduction及事实/身份上下文 | 当前已定义字段不提供视觉物件hard资格；素材参考/Voice身份沿已有类型化真实目录验证，不把公开事实投影成画面禁令 |
| Preparation自由文本/visual_constraints | 非主要派生上下文、postproduction | derived不能单独或加一个无关ID就充当硬授权；有合法主要依据仍须B判断相关性，程序不声称证明蕴含 |
| 本次真实程序默认/派生记录 | operational，仅对应记录的control或显式soft来源 | 记录规则版本、实际输入、输出path/值；A显式输入恰与默认相同也不获得此资格 |

Mode文档的“待解释资格”不等于强度证明；非主要条目只能伴随合法主要条目进入相应basis，不能靠数量拼凑资格。所有source_id必须已存在、唯一、数量0–4且范围合适。表中主来源资格由真实类型决定；缺少主来源时相关required/control不能ACCEPT。sourceID可选集合由程序按当前Need/scope和relation投影到Schema，程序消费者再校验同一规则。

**basis精确组合。** `basis`仅relation/source_ids，relation增加`operational`以闭合control合同。原文required仅upstream_obligation/director_realization且非空；preference仅preference，引用既有合法preference_source时允许source_ids为空（自由A软偏好本来就是合法偏好），否则须实际soft依据；postproduction仅postproduction，允许空依据但保留完整原句/对象上下文；unresolved仅unresolved且不用于推进。原文不接受operational。control输出只含id/status/basis，status为ACCEPT/UNRESOLVED；UNRESOLVED对应unresolved。ACCEPT按control真实消费者作用限定relation：硬过滤/源条件仅upstream_obligation/director_realization，程序实际默认/派生值可operational；既有明确soft只可preference或相符的soft操作记录；不能用postproduction/preference放行硬filter后继续保留它。非空依据及操作记录须与该control对应，缺失/错误即阻断整个Planning，不改原值。

**操作记录必须可复算。** 在parse及apply_defaults时由程序记录这一次实际执行的默认/派生：例如草稿确未填写desired_options而Pydantic应用1，或确缺preferred_style而Mode绑定既有soft默认。规则/输入/输出与原草稿字段存在性一并冻结。A明确写desired_options=1不是程序默认；media_type从模态kind派生只证明字段一致性，不证明模态语义选择正确；无操作记录不提供operational入口。身份纳入上述实际来源差异，不能把“缺省”和“显式自填常见值”混同以绕过审核。

**control作用与完整性。** importance影响required覆盖，duration_hint影响检索min_duration及生成时长，desired_options影响发现/候选数量；spec.kind/aspect_ratio/resolution/generate_audio/reference_asset_ids影响模态/生成参数与来源；constraints的orientation、尺寸/时长、source kind、allow_generation、logo/text_in_frame、identity及动态动作可影响检索/生成/Match。其他标量同样保留真实检索控制作用，不因未出现在已知Matcher表就被忽略。preferred_visual_details、preferred_style、visual_style按现有soft语义，不新增硬门槛。全部受审核值与同一最终Need快照/hash绑定，persist/load/缓存复算再次核验；不接受仅保存“审过”标签却读取另一份值。本文不改任何Provider映射或Matcher规则。

**无新增B请求的分批方式。** 原canonical单元仍按原40项/Need及40全局单元/批限制生成，原分批数量和映射不变；control单独有界，每视觉Need最多32项，全部放在该Need首次出现的既有B批次的controls数组，仅审核一次。一个批次含多个Need时controls汇总最多128项；超过或完整消息超过256 KiB时在提交前明确拒绝，不创建额外B批，不截断、不删要求。B输出classifications与controls分别严格完整/按序，修复Schema复用两组同样约束；repair仍只汇合受影响的既有批次。容量不用于宣称所有主题均能容纳；新合法样本若真实触界即保持FAIL并按证据处理。

**受验证的实际装载。** 从Attempt workspace/handoff调用已有verify_handoff_directory，核验manifest/hash及Creation/Handoff身份后读取其Creator/Truth/content/Mode files和production_request。Mode只用这个冻结目录及entries，不读全局当前Mode；brief同时核对manifest生产请求原件及planning_context既有brief SHA；video_plan按已有确认Schema/SHA与canonical一致性验证。只拿到hash而无真实正文时不建立可用条目，不允许A或评测替身补造正文。旧@1–6不装载或回填新目录；@7恢复使用同一真实原件重新建立目录并核对固定scope/hash。

**语义反例必须单列。** 引用A自证、未知ID、已知soft/隐私/derived单独硬化等属于程序应拒绝的结构/资格缺陷；B引用合法确认目标却错误把禁屏标director_realization，可以Schema合法、程序仍无法证明错误，独立语义Expected必须FAIL。本节不能把这个后者写成确定性程序必拒绝，也不能因允许这种受检验风险而改变R4零语义错误门槛。

### 13.26 来源组件实施进度（2026-10-07，未完成软件验收）

§13.25.1已获Astra前置CONTINUE，仅认可软件批实施；[复核记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-authority-design-review.txt)保留此前MODIFY闭合要求。未启动新真实R4、未加载新服务，也未改旧批成绩。

已新增应用层`planning_authority.py`：从实际已验证Attempt handoff读取确认/Mode/Creator/Truth/brief，构造有出处、范围和已知字段资格的目录；记录实际缺省与Mode绑定操作，枚举最终视觉控制值，校验basis资格及硬control不能由soft/postproduction放行。Mode名称属于元数据，不列为创作目标主要依据。operational核对typed值摘要，不能用False/0或1/1.0混同。

完整修前run036为116PASS/2新保护FAIL，旧115项无新增回归，sourceaff2与257现场/117fixture保持。组件run037为5PASS/2尚未接入FAIL；run038为6PASS/2尚未接入FAIL：实际历史原件、来源资格/scope、真默认与显式同值、硬filter控制、合法创意/错误realization语义边界、真实Handoff装载与篡改/伪上下文/孤立brief hash保护均已执行。每次均117fixture和257旧正式现场保持；最新工作树source `b878b38ba671a6e3a3acc2e4c2ae65b63666b2478613229c0f2c7e9b57c92898`只是未提交组件指纹，不是固定或已加载版本。

**未完成部分：** 新目录及controls尚未接入现有A/B运输、共享repair、请求/Plan身份、checkpoint复算和persist/load；第47行basis_transport/scalar_controls仍实际FAIL，不能认领0FAIL软件出口。下一步接入@7并补新原生连续链与旧@1–6恢复/跨批/容量保护，完成完整矩阵与全量回归后再固定版本、服务加载、新32项真实Eval。当前产品默认与服务仍旧固定89bc；未commit/push/restart，Smoke=NO。

### 13.27 @7 正式链集成及冻结前修订（2026-10-07，最终验收进行中）

在§13.25.1范围内已接入A/B、同一次共享repair、请求/Plan身份和checkpoint、正式persist/load。新产品工作树默认@7；没有版本参数的纯编译库API保留BASE@6兼容，产品执行及@7复算显式使用实际政策，不以缺依据切回旧版本。旧@1–6原件回放和旧pending不重派测试保留。现有旧风险fixture明确以@6执行；正常Owner/Gateway异步、repair及Supply/Observation连续集成采用产品默认@7。

@7来源装载核验实际Attempt/Handoff及冻结文件，scope/voice目录使用已验证Creator原件；正式恢复重新读取同一冻结来源、复算操作目录、Plan和全部B产物，不信任保存目录自证。复制仍在同一Creation/Handoff内，保留原origin且不重新Planning；persist之前尚未落盘的复制三文件仅允许使用与冻结scope/确认方案一致的参数，随后load核验实际文件。

第47行新依据运输及标量入口保护已通过；第48行执行真实内部保存/恢复/重入、单次repair、原pending身份、原件/目录篡改、漏basis/漏control、复制、跨批唯一control及受影响批次repair、纯声音B=0、混合模态/Voice字节绑定、每Need32/每批128/完整消息容量。无新模型调用、额度、Gate或Material Domain字段。fixture语义答案明确是外部固定回复，不证明真实模型改善；合法ID下错误realization独立FAIL仍保留。

run039因本次测试文件缩进错误未收集，失败原样保留；修正后run040为131PASS、run041为135PASS，257旧正式现场/117fixture均保持。首次全项目873PASS/5既有skip、115技能/compileall/diff通过，但不直接冻结该中间版本。Astra冻结前MODIFY指出：空controls的prefixItems不得为空数组、@7诊断必须列明controls/basis、完整B消息不能只检查JSON data容量。已最小修正，跨批初B/repair实际check_schema与validate，完整消息超限的真实内部调用证明所有B零提交；正在重新执行最终矩阵和全项目回归。

本节没有提交、加载服务或新真实R4。服务仍89bc；batch09及全部历史FAIL不变，Smoke=NO。最终软件通过及Astra结论、固定commit/source和真实新批结果分别登记，不把本节中间PASS当作真实发布成功。

**最终软件出口：** 修订后run042实际135PASS/0FAIL/0CONTRACT_GAP/0未执行；完整pytest873PASS/5既有skip，115技能、compileall、diff检查通过，未涉及前端。源203文件SHA`bf527ce1b565409817a5c21e0dc8029e6ca3ad73681bd619493fc4bd17be9caf`、257旧正式现场/117fixture在矩阵前后不变；Astra最终CONTINUE，无新增必修项。完整JUnit/stdout/source清单及结论见[单一软件记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-authority-software/software-summary.json)。此前run039/组件FAIL及batch09真实FAIL保留。下一步依既有授权窄提交、固定及安全加载，再以原16主题/原oracle另起全新32项，未完成真实成绩不得Smoke。

### 13.28 R4 batch10：@7固定版本已加载，真实评测进行中（2026-10-07）

固定commit`3be0ff946c29c8871a8f34de015c8b3944316ac7` / production203文件SHA`bf527ce1b565409817a5c21e0dc8029e6ca3ad73681bd619493fc4bd17be9caf`，23个选定源码/测试/fixture/Task文件凭证检查0命中，未push，其他工作树保留。run042135PASS/873全量PASS/5既有skip、115技能/compileall/diff、AstraCONTINUE。15:00:18 Web10168/Gateway10166安全加载，HTTP200/Gateway空闲；实际raw-stream停服后精确备份1,178,673字节、SHAbf6d88c5c98eeffb58971c3bc2ceb0dbf379d105c1dd847f3eab2d6d8dd0f0bf。无进程内SHA端点，版本证据为新PID/时间/执行文件/cwd与固定源核对。

实时8旧Owner有效操作0、各批unknown/pending/submitting/release待办0、Gatewayactive/lost/audit0，257旧正式现场/117fixture和九旧批原件保持。仅已购文字套餐额度89%/周98%，禁止余额/现金/超额/回退，实际账单UNKNOWN。原16主题与独立oracle不变，32新正常Creation隔离冻结，第0项开始真实Prep/A/B/Truth，尚无评分。正式合同与独立语义双PASS才下一项；实际Supply/Provider/生成/TTS/Build禁止，历史FAIL不恢复不倒算，Smoke=NO。[加载记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch10-release-loaded.json)。
