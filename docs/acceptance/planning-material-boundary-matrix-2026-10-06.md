# Planning → Material 边界合同与集成矩阵（2026-10-06）

当前：**统一治理软件合同PASS；现场保护FAIL，无例外整体验收不通过**。修复前历史：22 PASS / 1 FAIL / 2 CONTRACT_GAP。前三轮独立 Material E2E 的 FAIL 保留。本轮包含真实调度入口，未定义规则单列合同缺口，失败案例使用独立运行入口。

## 固定版本与范围

- 分支 easel-studio；commit `36ead76beaeed02ce53d1580dc4f0fb56ddcd88e`；生产源码集合 SHA `5f6e21a2fb301358c906291bbf4a811fa44ac986ace214a1c7ef687c10b0aede`。按全部 Git 跟踪 easel/web/scripts 路径→文件 SHA、排序紧凑 JSON 后再 SHA，与正式加载记录逐项一致。初稿带空格算法的不同摘要保留标注；文件未变。
- 本轮只调整测试、fixture、记录工具和文档；无 commit/push。223 个受保护文件（真实 Creation JSON 与前三轮 workspace）SHA 和文件集合不变；既有无关文档修改保留。
- Web PID45709、Gateway PID45701 仍为北京时间 21:04:30 启动的进程，无重启/加载。真实 E2E、采购、生成及视频执行均为零。
- 临时 Creation、存储、素材库；socket/外部进程/未替换 Gateway/真实 runtime 与配置路径有 fail-fast 保护，25 行均无触发。仅外部执行结果为确定性 fixture，内部生产模块使用真实实现。

## 重跑与判定

```bash
.venv/bin/python tests/planning_material_matrix/run.py
```

测试 CLI 支持 --output 保存运行记录、--case 选择局部案例；局部运行不算完整矩阵。无生产接口/schema/类型变更。

最终完整记录为 [run-009/results.json](fixtures/planning-material-matrix-2026-10-06/run-009/results.json)。同期保存 pytest 文本、JUnit、固定基线、对账与测试源码快照/SHA。失败返回非零退出码，不 xfail、不 skip；默认 collection 仍为736项，不包含 cases.py。源码快照使用 .py.txt，避免 pytest 加载历史 conftest。

矩阵25风险行、实际pytest25项。pytest 24 passed / 1 failed；两个执行通过但政策未裁决的项目单列 CONTRACT_GAP，不计 PASS，所以矩阵结果是22 PASS / 1 FAIL / 2 CONTRACT_GAP。

## 逐行 Expected / Actual

| ID | 案例 | Expected | Actual | 结果 |
|---|---|---|---|---|
| 01 | canonical / wrapper | 历史 wrapper 与 canonical 合同等价；7视觉与4声音完整保留 | contracts / all needs：{"visual":7,"all":11} | PASS |
| 02 | missing required / optional | required 原文漏项与 optional 视觉 ID 漏项均拒绝 | missing_visual：rejected; source unchanged；missing_required：rejected; source unchanged；partial_preference：rejected; source unchanged；whole required visual ID missing：rejected；no required Need in Plan：rejected after one bounded fixture repair | PASS |
| 03 | duplicate / unknown ID | 重复/未知 Need ID、重复 JSON 键、重复 Plan ID 拒绝 | duplicate：rejected；unknown_need：rejected；duplicate JSON / Plan ID：rejected | PASS |
| 04 | source binding | 错误 Attempt/冻结 refs/source path 拒绝 | wrong_identity：rejected；wrong_context：rejected；unknown_path：rejected | PASS |
| 05 | Unicode / 中文标点 | 中文标点逐字绑定；兼容具名引号漂移不允许真实改词或漏引号 | need types / importance：[["image","image","required"]]；visual contracts：1；canonical punctuation mutation：rejected | PASS |
| 06 | path alias / null | 已定义 wrapper path/空引用适配；canonical 非法 alias、空/未知引用拒绝 | path:modality_spec/visual_style：rejected canonical variant；preference_path:：rejected canonical variant；preference_path:unknown：rejected canonical variant | PASS |
| 07 | visual only | 纯视觉 Plan 可编译，原 Need 不变 | need types / importance：[["image","image","required"]]；visual contracts：1 | PASS |
| 08 | visual + narration | visual + Voice 合法；Voice 参数不进入检索 filter 或 visual sidecar | need types / importance：[["image","image","required"],["voice","audio","required"]]；visual contracts：1 | PASS |
| 09 | visual + BGM | visual + BGM 合法；BGM 保留自身偏好及 no-vocals 检索语义 | need types / importance：[["image","image","required"],["bgm","audio","required"]]；visual contracts：1 | PASS |
| 10 | image/video + Voice/BGM/SFX | image/video/Voice/BGM/SFX 与 required/optional 完整保留；audio 不进 canonical visual map | need types / importance：[["image","image","required"],["video","video","optional"],["voice","audio","required"],["bgm","audio","required"],["sfx","audio","required"]]；visual contracts：2；audio ID in canonical visual map：rejected | PASS |
| 11 | required/preference/postproduction/unresolved | 四类职责分离；明确源动作不得交后期；unresolved 不提交观察 | explicit preference promoted to required：rejected；unresolved / dynamic action：blocked before observation | PASS |
| 12 | query/provider/ranking metadata | 查询元数据不进入视觉原文；已定义查询对象不进入硬 filters；未知 provider/ranking 协议单列 | retrieval filters：{"media_type":"image","search_query_variants_primary":"paper daylight","search_query_variants_alternate":"pages room","search_query_variants_relaxed":"documents indoors","required_source_kind":"stock","usage":"internal"}；top-level provider/ranking：rejected; structured unknown constraints rejected | CONTRACT_GAP |
| 13 | 三类 Mode 默认 | 仅视觉/仅声音/混合 Mode 的默认值在真实 persist 后按模态保留，与 producer cache 一致 | mode 0：{"need_ids":["image","voice","bgm","sfx"],"producer_consumer_key_equal":true}；mode 1：{"need_ids":["image","voice","bgm","sfx"],"producer_consumer_key_equal":true}；mode 2：{"need_ids":["image","voice","bgm","sfx"],"producer_consumer_key_equal":true} | PASS |
| 14 | producer/consumer cache | 同轮合同零额外分类；legacy 重验可用；坏新 cache 不绕过 | current：7 visual consumer checked; corrupt new cache rejected；legacy：7 visual consumer checked; corrupt new cache rejected；corrupt_current：7 visual consumer checked; corrupt new cache rejected | PASS |
| 15 | revision / cache identity | 相关 Need/refs/Mode 输入变化使 cache 与正式 Plan revision 失效；不强制无关局部缓存失效 | Need：new cache identity; old key not selected；refs：new cache identity; old key not selected；Mode：new cache identity; old key not selected；policy-only revision：formal revision changes; unchanged local source contract may reuse；actual persisted Planning load：changed Plan revision and changed SCRIPT bytes both rejected | PASS |
| 16 | schema / unknown modality | 未知 modality、类型错配与额外 schema 包装拒绝 | unknown / mismatch / wrapper：all rejected | PASS |
| 17 | 历史声音对象污染 | 第二轮真实跨模态对象提前拒绝，原件不变；合法 Voice 独立编译 | historical object plan：rejected before visual contract; canonical Voice accepted | PASS |
| 18 | 历史扁平声音别名 | 第二轮真实扁平别名全模态拒绝，原件不变 | historical alias plan：rejected before consumer | PASS |
| 19 | Voice 文稿引用与摘要 | Voice 文稿引用/摘要必须配对；persist 绑定当前 SCRIPT、保持声音身份 | second-run initial Planning archived JSON (serialized representation)：Voice text_ref without text_sha256 rejected by actual JSON Domain validator；frozen Voice binding：{"kind":"voice","identity":{"source":"director_intent","reference":"测试预置声音，不是实际调用","reference_asset_ids":[],"consent_ref":null},"delivery_description":null,"text_ref":"planning/SCRIPT.md","text_sha256":"e4087309e730e039ef304b11a459ff5164cb529472982dc4001405f48888feb4"} | PASS |
| 20 | missing sidecar | 核实缺失同轮 sidecar 的实际行为与新/旧路径契约冲突，不自设放行规则 | missing sidecar：executor accepts; no same-turn requirements cache | CONTRACT_GAP |
| 21 | 第三轮确认稿解析 | 确认前拒绝明确混入旁白的制作说明，不从已确认稿自动删字 | clean / recognized instruction heading controls：accepted / rejected；normal parser：{"accepted":true,"script_contains_meta":true}；test-only equivalent instruction labels：{"original":true,"制作备注":true,"配音说明":true}；断言失败，说明仍被 parser 接受 | FAIL |
| 22 | 第三轮 Truth 与冻结稿 | 原 Truth 报告仅绑定原脚本，冻结稿需重写时停止；不冒充人工放行 | actual stop：{"rewrite_required":2,"unresolved":1,"supply_calls":0,"fixture_gateway_calls":1} | PASS |
| 23 | 冻结原文篡改 | 未冻结错误草稿可归档恢复；冻结后任何真实改字必须拒绝，不覆盖现场 | unfrozen restore / frozen tamper：archived then restored / rejected without overwrite | PASS |
| 24 | Owner→Supply→Observation | 正常新测试 Creation 经真实确认、Owner、Preparation、Planning、persist、Supply、首轮 observation；无 Authoring | actual pipeline：{"operations":["prepare","observe_material"],"gateway_fixture_calls":["preparation","planning","truth"],"supply_calls":1,"observation_calls":1,"planning":{"status":"PLANNING_READY","plan_id":"plan-293de79cde722ccf02cb","plan_revision":"6d8b6be14a211552c3198d2636d0945d1b20d03736ef9ce56dbb2195791011bd","manifest":"planning/manifest.json","truth_review_status":"PASSED","truth_ledger_locator":"planning/script-claims.json","truth_ledger_sha256":"c1f15acf29026275edb4b5c664f91883aa8efee9fbc7d22f51b976259a12a50b","script_sha256":"e13544b58e1148dc4b5a891821c07353a310ea9f8e9540cd583a28145d498b53","truth_packet_sha256":"ce8b9df3c787bf6ffe009ab421b36fe6ac63dfa7bd9f5e99f3bd90c9ea12a737","truth_claim_count":1},"gate":"MATERIAL_NOT_READY"}；completed prepare re-entry：{"supply_service_entries":2,"provider_searches_before_after":[1,1],"acquisitions_before_after":[1,1],"gateway_fixture_calls":["preparation","planning","truth"]} | PASS |
| 25 | 中断恢复 / 重入 | pending/timeout/complete/failed 重入只恢复原请求；错误或草稿变化不新增额度 | valid：same durable request observed twice; complete/failed do not redispatch；invalid：same durable request observed twice; complete/failed do not redispatch；pending_valid：same durable request observed twice; complete/failed do not redispatch；timeout：same durable request observed twice; complete/failed do not redispatch；failed：same durable request observed twice; complete/failed do not redispatch；native durable Gateway adapter + Owner next_operation：one agent submit; same-run waits; unrelated run/profile rejected; completed result reused; runtime released | PASS |

具体合同依据、phase 状态、异常栈与调用证据见机器结果。正确拒绝非法输入记 PASS；测试替身的语义结论不作为新的正式审核。

## 根因聚类与统一修复建议（未实施）

### F1：确认正文与制作说明职责混合 — 明确 FAIL（21）

第三轮原始正常 proposal 被 `parse_video_plan` 接受，script 包含 `**说明**`、字数说明、未来 TTS 时长及编排指令。隔离变体把标题改为“制作备注”“配音说明”仍被接受；纯文案正例通过，已有“旁白说明”标题被拒绝。入口依据为 [creator_proposal.py](../../easel/creator_proposal.py#L96) 明确的“确认前拒绝混合旁白/指令”规则，实际关键词拦截范围不足。

之后 [app.py](../../web/app.py#L3097) 将确认字段全文恢复成 SCRIPT；原报告身份有效，但冻结保护在 rewrite_required 时阻止改字。第22行正确回放了这个停止点和旧报告不能认领改字脚本的约束。冻结保护没有坏，不能以删除保护作为修复；原报告回放也不证明每项模型语义判断正确。

最小建议：在方案生成、预览与确认前明确“逐字朗读正文”和说明/编排的位置，使用同一入口合同验证。入口对整类混排有确定行为，不能只给 **说明** 再加一个关键词。确认前可以拒绝当前草稿并通过正常方案修订纠正；确认后不猜测删字，冻结稿继续严格保护。确切实现留给统一修复 Task，本阶段未实施。

### G1：query 元数据兼容与检索角色 — CONTRACT_GAP（12）

`sources_for` 排除了所有已知 query 字段。NeedCompiler 排除了 canonical search_query_en 和结构化 search_query_variants_en，但旧三标量 primary/alternate/relaxed 被一般 scalar 分支放入 filters，见 [compiler.py](../../easel/materials/application/compiler.py#L48)。顶层 provider/ranking 和未知结构化 metadata 均正确拒绝。

事实是旧字段在两侧角色不同。尚未证明具体 Provider 因未知 filters 拒收或导致覆盖降低，因此先列合同缺口。需裁决旧三字段仅作兼容运输还是正式检索输入，再统一现有 NeedCompiler/consumer 边界；建议它们属于检索提示，不扩大视觉必要要求、不制造 required 条款。不能由本轮测试自行新增 Domain 字段或规则。

### G2：新 Planning 的 sidecar 必需性与旧恢复路径 — CONTRACT_GAP（20）

producer 要求同轮 MATERIAL_REQUIREMENTS，但 [app.py](../../web/app.py#L3305) 只在文件存在时校验。第三轮合法 Plan 删除 sidecar 的隔离变体被 executor 接受，没有同轮合同缓存；已有旧路径允许 observation 后续分类。因此“新 Planning 必须同轮交付”与“旧 checkpoint 可恢复”未形成明确、可验证的身份/版本区分。

建议先明确新任务与合法旧 checkpoint 的兼容政策，再在既有入口实现。不能泛化为任何缺失文件都放行，也不能直接破坏旧恢复；正式裁决前保留 CONTRACT_GAP。

### 历史已修问题的分布

- **运输与来源绑定**：第一轮 wrapper、audio 混入、path/null/Unicode、query 被当视觉原文及 producer/consumer cache 的当前回放通过；保留全部 Need/importance 与原件。
- **模态职责**：第二轮声音对象、扁平别名、初始 Voice 引用配对错误确定拒绝；合法参数、默认值和冻结脚本绑定通过。拒绝原非法 Plan 不改变原 E2E 的 FAIL。
- **执行身份与重入**：五种结构修复结果保持同一持久请求；真实 durable Gateway adapter 的 timeout/未知 run/完成复用/释放回放只提交一次 agent，后续观察原 run。

当前基线上确认的是 **1 个代码行为 FAIL + 2 个合同政策缺口**。不能据此认定历史问题只有一个根因，或必定由两三个补丁解决；自然语言分类与真实外部能力仍有验证边界。后续统一评审 F1/G1/G2 的最小范围，涉及跨模块合同/责任边界时先按 AGENTS.md 做 Astra 复核，再实施并回归整个矩阵。

## 调度入口与真实模块交接证据

第24行使用真实创建、方案保存、显式确认与素材终点 API；经 Owner advance_creation 和 Web dispatcher 进入 Preparation draft 校验/冻结、Handoff/Attempt、真实 Planning executor、Truth 合同、PlanningIntegration.persist、ProductMaterialSupply、接收/技术检查/Bundle/Gate，最后进入首轮 compact Observation。外部准备/Planning/Truth 响应和观察语义仅为确定性 fixture。

实际操作为 `prepare → observe_material`；Gateway fixture 3次（Preparation/Planning/Truth），LocalProvider.search 1次、MaterialAcquirer.acquire 1次、Observation 1次，只有一个 Attempt。同轮合同由 consumer 使用，没有额外要求分类。Rights 保持 UNKNOWN，观察返回 unknown，Gate 保持 MATERIAL_NOT_READY，没有伪造素材满足或 MATERIAL_READY。

已完成 prepare 再次进入供给服务，总服务进入2次；实际搜索和接收均为1→1，原结果复用。服务进入次数与外部重复工作分别计量。Authoring/Build/Quality/Selected Output 未执行。第25行另外覆盖持久 repair 与真实 adapter/Owner next_operation 的未知、超时与终态恢复。

## Fixture 与装配记录

前两轮已有 fixture 原样复用。新增第二轮 INITIAL 保存实际 text_ref 非空而 text_sha256=null 的事故，来自原受保护归档重新序列化的 JSON；原运行 SHA 与复制件 SHA 明确区分。第三轮新增 manifest、proposal、确认字段、SCRIPT/SCENES/TREATMENT、Plan/sidecar、Truth 与原报告，原字节项逐项与 archive SHA 对照。测试派生变体不回写 fixture 或真实作品。

所有早期运行日志与失败保留：

| 运行 | 装配或覆盖变化 | 结论处理 |
|---|---|---|
| 001 | next_operation tuple 读取和子临时目录未创建两处装配错误 | 保留异常，修正测试 |
| 002 | 将供给服务进入次数误当外部搜索次数 | 根据源代码与实测改计 Provider.search/acquire，不改生产 |
| 003/004 | 补 revision/SCRIPT 身份拒绝、无 required Plan、真实 durable adapter 回放 | 已通过部分保持；产品 FAIL 保留 |
| 005 | 新 INITIAL fixture 把归档版本名当文件字节 SHA，复制中止 | 明确重新序列化来源与两种 SHA，补全原归档复制；事故不修正 |
| 006/007 | 初始配对事故、说明标题变体与配置路径保护补齐 | 产品 FAIL 保留 |
| 008 | 保存工具源快照；默认 collection 发现复制的 conftest.py 被自动加载 | 初次 collection 错误保留；快照改用 .py.txt，字节/SHA 保持 |
| 009 | 最终完整矩阵与源快照，默认 collection 复核成功 | 正式结果22 PASS / 1 FAIL / 2 GAP |

这些是离线测试装配修正和覆盖补齐，不是工程恢复真实作品；生产实现没有修复。各次受保护现场对账均未变。最终 pytest 1.11秒（不含调查/装配时间），测试 compileall、默认736项收集隔离、git diff --check 通过；27份最小 fixture/最终运行文件脱敏检查无 Secret，未替换外部/配置访问尝试为0。未重跑全量常规测试。

## 限制与停点

结构/span/hash 测试不能证明模型会正确理解 required/preference/postproduction、审阅事实或评价实际视觉/声音。测试显式给出的分类仅用于保护交接合同，不是语义能力证据。Provider/生成/ASR/BGM 能力、真实耗时及 Rights/Match/Readiness 自主完整成立仍须后续验收。

本轮已完成测试、记录与聚类，停在统一修复建议。下一步先裁决两个合同缺口，再统一最小修复并回归矩阵；软件通过后另行固定版本/预算授权进行 Material Smoke，再跑完整独立 Material E2E。第三轮预算不转授，不恢复旧 FAIL，不进入视频或扩 Provider。

## 统一治理A–D软件交付（2026-10-06）

本节是用户确认统一Task后执行的独立软件记录。前文run-009、三轮原FAIL及原合同缺口调查不改写，不将测试fixture的判断当成真实模型或Provider验收。

```ini
SOFTWARE_CONTRACTS = PASS
F1 = CLOSED
G1 = CLOSED
G2 = CLOSED
MATRIX = 25 PASS / 0 FAIL / 0 CONTRACT_GAP / 0 NOT_EXECUTED
SCENE_PROTECTION = FAIL
OVERALL_EXCEPTION_FREE_ACCEPTANCE = NO
REAL_EVALUATION_SMOKE_E2E = NOT_STARTED
REAL_MATERIAL_READY = NOT_CLAIMED
COMMIT_PUSH_SERVICE_RELOAD = NOT_PERFORMED
```

### 固定版本与执行证据

沿用easel-studio HEAD`36ead76beaeed02ce53d1580dc4f0fb56ddcd88e`，改动保持未提交，并保留用户既有文档整理。A基线tracked production SHA为`5f6e21a2fb301358c906291bbf4a811fa44ac986ace214a1c7ef687c10b0aede`。最终包含新增三份源码的201文件集合SHA为`cd314b19e591a302657c4762508ac42b0df422139d8ebe44a89b86991c45aecc`；仅原tracked文件算法为`f69d959fd4d14dcc13a6b9695ba44147a3f6e08b712219b42c5f3788647bcb38`。run-012起执行器补入untracked且非ignored源码，避免遗漏新helper；原run快照与算法不重写，两个指纹不能混作同一文件集合。

| 批次/记录 | 结果与用途 |
| --- | --- |
| A/run-010 | 21 PASS/4 FAIL/0 GAP；先按批准合同固定期望，失败为query硬filters、缺sidecar、混排确认稿、新Attempt缺v2登记 |
| A/governance-baseline-pytest | 731 passed/5既有skip/2新增失败；完整不回归基线与新增合同反例，45.18秒 |
| B/Astra | 前置CONTINUE；固定拒绝旧ready自动重规划、原pending先核实、Mode最终身份与报告早返保护 |
| C/governance-c-second-pytest | 226 passed，16.71秒；相关Preparation/Material合同与集成，不代替D全量 |
| C/run-011 | 25 PASS；第一次完整修复矩阵，通过不覆盖后续发现的合法路径缺陷 |
| D首轮与补证 | 保留governance-d-pytest和targeted/order失败；补外部Planning fixture的第五文件、修复canonical字段排序及副本v2兼容，绝不删除失败证据 |
| D/run-015 | 25 PASS/0 FAIL/0 GAP/0未执行，1.35秒；全部必验行实际执行，无skip/xfail |
| D/governance-d-protected-pytest | 738 passed/5既有skip，49.41秒；缺bun的5项微信发布器配置检查，不属于本期必验行；2项既有Starlette弃用warning |
| D常规检查 | 115技能合同、compileall、diff PASS；无frontend源码变化，lint/build不适用 |
| 最终Astra | CONTINUE仅认可软件合同冻结；明确现场保护FAIL，不能认领无例外A–D通过 |

所有日志、JUnit、Expected/Actual、harness及新helper快照存于[单一证据目录](fixtures/planning-material-matrix-2026-10-06)。最新[run-015机器结果](fixtures/planning-material-matrix-2026-10-06/run-015/results.json)、[全量日志](fixtures/planning-material-matrix-2026-10-06/governance-d-protected-pytest.txt)、[软件对账](fixtures/planning-material-matrix-2026-10-06/governance-software-audit.json)共同构成证据，构建或静态检查不替代集成。矩阵使用真实内部模块；只在外部执行边界替换结果。常规回归直接复用matrix24场景，G1/G2共享断言也复用于原矩阵，未增加第二执行器。

### 三个根因关闭与不回归

**F1：** 新五栏目方案用@2 literal text容器，提取只移除容器两处换行，保留正文空格、中文标点、LF/CRLF与块内标题。历史原混排及原SCRIPT包入合法容器仍拒绝；独立说明标签和加粗结构受保护，合法台词含“说明/配音”不误拒。保存/预览/确认重验；无效更新不能沿用上一版可确认标记，旧未确认稿正常修订，已确认v1可读/重放不迁移。真实确认→Owner→Planning→persist→load→Observation的SCRIPT字节一致，CRLF与Voice文本SHA有断言；旁白/屏幕文案/无字正例及既有声音集成通过。没有新增确认前模型审核。

**G1：** compiler、visual sources和recovery共用query_hints；canonical三变体优先、旧有序部分组/去重/校验其次、单query最后。候选最多4与原英文稳定排序保持。known query不进入硬filters、negative terms或视觉required，所有其他源约束不变。真实Supply的Provider实参验证legacy query与filters；人工标注的旧query-as-filter receipt不命中新compiled输入，新合法receipt第二次零额外搜索。Need原件未改、未迁移Plan或清库。

**G2：** 新产品执行登记v2，缺sidecar进入已有一次结构修复，耗尽或不完整时拒绝Supply。persist校验全部视觉Need和Mode最终默认，保留原Need来源并按canonical落盘表示绑定cache；Attempt与manifest绑定版本/SHA/revision/Truth/sidecar。真实Owner可进入Supply/首轮Observation；观察UNKNOWN与Rights UNKNOWN保持，Gate为MATERIAL_NOT_READY，不伪造真实准入。删除/损坏sidecar、版本降级含删除全部标记、Attempt状态/Plan/revision/SHA错配、坏cache与异源Need均拒绝，已有报告早返也先核验。丢失派生cache从有效sidecar确定性重建，零模型分类。

有效合成v1 checkpoint按原字段恢复，不回填SHA；v1坏检索不得重新派发。旧pending initial先按原profile/run重复观察，终态释放后才登记v2；旧pending repair在当前route变化时也先观察原运行，再停止，不刷新额度。已有耐久Gateway场景保留一次提交、同run wait、未知提交/错run/错profile保护。既有v2合法checkpoint副本保存原sidecar字节和默认前source_needs，核对源冻结SHA；wrapper先校验可信origin，再内存绑定新Attempt。复制期间目标字节变化拒绝并可按原副本请求重入，不改源作品。该行为仅由既有三内容隔离软件回归验证，没有启动真实视频。

内部OutputDecision统一四类解释，状态推进继续由原业务校验器决定。proposal保存ACCEPT/REJECT，Preparation snapshot/错误、Planning有效输入/已知wrapper及单次repair、Truth报告、Material持久入口接入原返回与记录；没有额外状态机或模型网关。原结构化冻结摘要/报告引用仍为正式证据；没有独立输入文本的诊断摘要为null，不复制用户全文进普通日志。

主连续场景：外部Gateway fixture为Preparation/Planning/Truth各1，真实LocalProvider.search/MaterialAcquirer.acquire/compact Observation各1；完成prepare重入服务可再进入，但搜索/接收仍各1，额外视觉分类0。G1 cache单独场景搜索1后合法复用0。pending新补证为原run wait5、终态runtime release2、提交0，repair记录不变。其余25行及费用、Rights/授权/身份/准入/下游保护由原矩阵和全量测试实际运行，无法以这些fixture数字推算真实费用或覆盖率。真实模型/Provider/采购/生成调用0、实际新增外部费用0，历史费用不清零。

### 现场保护事故：FAIL，未恢复或掩盖

2026-10-06 23:01:30（UTC15:01:30），首轮D全量测试导入了当时尚未限制产品范围的Web v2登记分支。两项历史fixture使用真实Creation/Attempt ID，调用service.update_film_attempt后误写正式Creation元数据：第一轮3个、第二轮15个planning_contract_registered事件，以及planning_contract_version=2、Attempt.updated_at、Creation.updated_at。该时点发生在run-012之后、run-013之前；单个matrix运行前后相等不能证明整个A–D始终未碰现场。

最终223个受保护文件中221份与A基线一致，两份creation.json不一致；19份历史fixture、三轮workspace文件、Plan/Need、素材、Truth/审核、授权/费用及三轮failed终态保持。利用旧脱敏归档的原更新时间，只在内存中去掉事故登记字段/事件并还原时间，重新序列化能**精确复现A基线SHA**，证明变化范围仅为上述四类路径。没有回写这些反事实对象，没有恢复/Retry旧作品或倒算原FAIL。

[事故机器记录](fixtures/planning-material-matrix-2026-10-06/governance-runtime-integrity-incident.json)保留原SHA、当前SHA、事件数量、四类路径和来源归档位置。修正为只登记真实产品Planning，随后在tests/conftest.py加入常规测试对真实runtime打开写入/OS文件描述符写入/rename/replace的禁止保护；该保护器不是完整文件系统沙箱。最终run-015与受保护全量前后全部运行文件保持事故后状态，没有进一步变化。

因此软件合同0 FAIL与**现场保护FAIL**同时成立；本轮不能宣布A–D无例外整体成功，更不能宣布独立Material E2E成功。两份真实Creation元数据保持事故后状态，处置另行由用户决定；本轮不自动恢复、改数据库或伪补证据。

### 停点

完成软件实现、回归、冻结复核与事故审计后停止。未commit/push、加载/重启Web或Gateway、真实评测、Smoke、独立E2E、素材采购/生成或真实Authoring/Build/Quality/Selected Output。三个原E2E保持FAIL；真实MATERIAL_READY与自主交付仍未验收。E批和服务加载不因软件合同PASS自动启动。

## 固定版本与服务加载（2026-10-06，用户另行授权）

事故处置结论为 `CLOSED_WITH_RETAINED_EXCEPTION`：保留两份旧Creation事故后元数据，不恢复、不Retry、不复用；历史 `SCENE_PROTECTION=FAIL`、A–D无例外整体验收NO及三轮真实E2E FAIL不改写。只读核对7个已登记Delivery，按next_operation与advance_creation持久失败额度推导均无新操作、无状态改写；pending/submitting及runtime_release=pending均为0。未登记作品不由Owner自动推进。

代码固定提交为 `55af28fb62bf4bd0d194b372101a55b05a48a051`（easel-studio，未push），201份production source集合SHA仍为 `cd314b19e591a302657c4762508ac42b0df422139d8ebe44a89b86991c45aecc`，与run-015完全一致，production工作树干净。仅提交本Task源码、测试、fixture和脱敏证据，其他既有文档修改保持。已知本地凭证比对扫描164份文件0命中、无凭证/数据库/生成媒体/cache纳入；源码/测试/说明diff检查通过，历史pytest/XML/diff捕获件保留原始尾部空格，不改验收原件。

Astra只读CONTINUE，落实Owner推导、待释放运行检查、日志保护及源指纹条件。沿用现有 `ai.openclaw.easel` / `com.easel.web` LaunchAgent，通过launchctl kickstart加载，不改配置。原始Gateway/Web/raw-stream日志在仓库外700目录/600文件备份并核对SHA，未进入Git。Gateway PID61470（23:35:16），Web PID61558（23:35:27）；Web执行路径与cwd为本仓库，Gateway版本2026.9.4。Gateway是OpenClaw运行时，并不直接加载Easel Python模块；其wrapper指纹另记。无进程内源码SHA接口，以新进程、LaunchAgent路径及加载前后源码指纹提供加载证据。

23:36加载后健康检查通过，7秒Owner循环观察无推进；Gateway 669任务均终态，active/queued/lost=0，审计warnings/errors=0。加载前当前registry为671，历史终态计数存在变化，不把注册表总量当永久调用账本；本轮不发起模型任务。223份受保护文件全部保持事故后加载基线，19份历史fixture不变；不将本轮不变解释为A–D现场从未改变。真实评测/Smoke/E2E/采购/生成/视频均未启动，新增付费调用0。

[脱敏加载记录](fixtures/planning-material-matrix-2026-10-06/governance-release-loaded.json)。完整本地preflight/loaded及日志备份在 `/Users/xgx/Library/Application Support/Easel/acceptance/output-governance-release-2026-10-06`。版本加载前置检查PASS；下一步制定真实模型评测样本、预期、调用上限/预算及停止条件，另行启动，不认领真实MATERIAL_READY。

## R0–R3 单一语义源软件验收（2026-10-07）

用户“设定目标并且按照文档进行实施”授权本Task第十一节R0–R3。**SOFTWARE_ACCEPTED=YES；真实模型可靠性、服务加载及MATERIAL_READY未认领。** 使用同一Task、同一矩阵执行器和本验收入口；前三轮E2E FAIL、第四轮Planning失败及历史现场保护FAIL例外全部保留。

### 基线、先失败证据和根因

R0固定HEAD `55af28fb62bf4bd0d194b372101a55b05a48a051`、201文件源码SHA `cd314b19e591a302657c4762508ac42b0df422139d8ebe44a89b86991c45aecc`，只读纳入第四轮原Plan、要求文件和持久repair。脱敏fixture在 `tests/fixtures/planning-semantic-contract-2026-10-07`，manifest区分原件SHA/fixture SHA；初始输出缺失，未虚构。旧合同回放仍拒绝不存在的 `constraints/subtitle_overlay_only`；真实repair消息先报Voice schema，不能说同一path曾反复修复。R0原始测试 **1 PASS/1 FAIL（新协议未实现）** 保留于 [r0-first.txt](fixtures/planning-material-matrix-2026-10-06/r-batch/r0-first.txt)，之后才修改生产。

原25风险行和历史run-009/run-015未替换。针对性日志记录了检查点JSON元组/列表比较导致重入误判，以及人工正确对照错用SFX global scope等测试缺陷；都保留首轮失败记录，按正式合同修正，不修改历史预期。

### 实现与合法路径保护

产品v3执行：**A单份语义草稿 → 程序绑定身份/模态/默认值/Voice正文摘要与来源快照 → B只分类程序unit ID → 程序完整汇合并复用bind/validate → canonical Plan/Requirements/cache/manifest → Truth及现有Delivery判断。** 模型不再交付正式Need ID、source_path、原文副本或正式sidecar。B每批最多40单元，保留相关Need完整上下文，256 KiB应用层有界容量，不能截断要求；純声音B=0。总Planning最多 `1+B批数+1共享repair`，Truth单列；有界额度不是实际网关通用容量保证，真实Eval仍要核实模型/网关行为。

Voice只选择可信Creator Context voice或具名上下文的既有identity来源；reference/参考素材/consent核验，不从任意非空Treatment制造授权。旧v1/v2已冻结/旧确认路径继续按原合同，已有旧terminal/error/release pending/Plan/sidecar/repair不登记v3。新正常@2方案登记v3；失败不降级。v3已有报告/缓存早返仍先校验完整合同，checkpoint副本显式验证源身份后绑定新Attempt；不迁移历史产物。

修复共享原Attempt账本与单次额度，未知先核对原请求。保护完整Need数量/顺序及原有效语义，包括嵌套Optional模型、策略、声音有效子参数；只允许纠正无效字段。A修复首次与恢复执行相同保护；B及其修复不能修改有效草稿。损坏原件/冲突摘要不能覆盖；半产物不提交ready。没有新增公开路由、框架、状态机，Material V1.3/required/Rights/Match/Readiness及预算语义保持。

独立答案包含两张白纸、叙事用途与暖光软偏好、动态源动作反例、Voice/BGM/SFX及混合模态。不能用编译器枚举的source再自产expected来证明语义正确；旧装配型测试仍保留其原范围。

### 最终实际执行

| 验证 | 最终结果 | 证据 |
| --- | --- | --- |
| 唯一完整矩阵 | **53 PASS / 0 FAIL / 0 CONTRACT_GAP / 0 NOT_EXECUTED**，36风险组含参数化；原25组保留 | [run-017结果](fixtures/planning-material-matrix-2026-10-06/run-017/results.json)、同目录pytest/JUnit/harness/baseline/reconciliation |
| 常规pytest | **787 passed / 0 failed / 5既有skip**，55.98秒 | [原始日志](fixtures/planning-material-matrix-2026-10-06/r-batch/full-validated.txt)、[JUnit](fixtures/planning-material-matrix-2026-10-06/r-batch/full-validated-junit.xml) |
| 新协议针对性回归 | **49 PASS**，2.19秒 | [r2-targeted-12.txt](fixtures/planning-material-matrix-2026-10-06/r-batch/r2-targeted-12.txt) |
| 技能合同 | 115 PASS | [skills.txt](fixtures/planning-material-matrix-2026-10-06/r-batch/skills.txt) |
| compileall / diff检查 | PASS；未改前端，不需要新增lint/build | r-batch/compileall-final.txt；最终diff检查退出0 |
| Astra实际实现复核 | 两轮MODIFY修正后 **CONTINUE** | [复核摘要](fixtures/planning-material-matrix-2026-10-06/r-batch/astra-review.json) |
| R0至最终现场对账 | **257/257文件未变**；原19历史fixture未变，新增后24fixture矩阵前后不变 | [reconciliation.json](fixtures/planning-material-matrix-2026-10-06/r-batch/reconciliation.json) |

5项skip均为既有publisher `bun is not installed` 场景，不属于R批必验合同/集成场景；矩阵无skip/xfail。保留2项既有FastAPI/Starlette弃用warning。没有用单测或构建替代连续集成。

v3连续集成实际执行正常方案确认、Owner、Preparation、A、B、Truth、persist/load、Supply、首轮Observation；仅外部Gateway/模型/观察响应替身，Local Provider搜索与接收及内部校验真实。Gateway fixture四次为Preparation/A/B/Truth各1；实际检索/接收/观察各1。完成prepare重入可再次进入供料服务，但搜索/接收保持1→1；Gate仍MATERIAL_NOT_READY、Rights UNKNOWN，不伪造素材准入。

另通过真实内部 `run_delivery_agent`、仅替换RPC的提交超时与终态release超时：A/B共两次agent提交，重入只核对原run/request SHA，全部runtime released，不重新提交。原始直接dispatch恢复测试与该实际适配器证据分别保留。40+1单元跨批Plan保留required/optional，失败只修受影响批次、正确响应字节不变；A+两批B+repair共4次，完成重入0新增。纯声音A一次，正式Voice/BGM/SFX仍各自保留。

Astra具名发现并要求修正：A语义保护重入绕过、有效字段/嵌套子字段保护不全、旧执行误登记v3及真实适配器证据缺口。已加入首次拒绝/恢复仍拒绝与合法修复正例，不用删除测试或放宽合同消除FAIL。最终CONTINUE只允许软件冻结，不授权真实执行。

### 源码指纹与停点

软件验收source集合：**202文件 SHA `0907c35cf4ee98254ac0a598f924d7b757b4aaf29cc24d1ac1d3f234d5e65217`**。HEAD仍为55af28fb，新实现处于未提交工作树；[完整源码清单](fixtures/planning-material-matrix-2026-10-06/r-batch/reconciliation.json)与[确切生产差异](fixtures/planning-material-matrix-2026-10-06/r-batch/production-diff.patch)形成可回查软件指纹，**不是新的已提交发布版本**。没有commit/push或主动重启/加载服务，实际运行版本未重新核验。新文件模式扫描35文件0凭证模式命中，未读凭证配置；这是模式检查，不等同于真实凭证值比对。用户其他既有工作树修改保留。

[机器验收汇总](fixtures/planning-material-matrix-2026-10-06/r-batch/software-acceptance.json)。本轮真实模型/Provider/采购/生成调用0，新增付费外部费用0，新真实Creation 0；旧作品未恢复/Retry/补证。历史现场保护FAIL保留例外，本轮现场不变不能倒算历史无事故。

**停止于R0–R3软件验收。** 下一步另行固定提交与检查服务加载，再按Task §11.8冻结16主题/32次独立Planning Eval及预算；Eval不搜索/生成/TTS，通过后才启动Material Smoke，再独立Material E2E。当前真实Eval/Smoke/E2E=NOT_EXECUTED，AUTONOMOUS_DELIVERY/MATERIAL_READY未验收；Creator意图的模型泛化仍须独立留出检查。
