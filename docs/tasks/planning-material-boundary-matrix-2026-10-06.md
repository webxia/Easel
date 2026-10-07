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
