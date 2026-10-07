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
