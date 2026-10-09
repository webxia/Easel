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


## R4 异步前置验证失败（2026-10-07，固定版本STOP）

旧真实批次的评测工具FAIL及费用记录保持。后续只补评测工具的持久状态分类、原生Owner检查点循环和原始客户端执行归档；新真实批次尚未启动。新增内部集成仅在外部RPC transport/CLI入口和运行环境使用fixture，实际执行Owner、Preparation冻结/恢复、Gateway账本和Planning消费者。

发现生产缺陷：首次Preparation返回未排序的内存bundle，恢复读取已排序冻结文件。完整A JSON解析值相等，仅voice.context键序 `tone,avoid → avoid,tone`，请求文本SHA改变。生产 `invoke`因重建请求字节不符拒绝，原A已ok/released仍不能继续。这是生产恢复缺陷，不是模型语义缺陷，也不能通过修改fixture或放宽身份保护消除。

证据为[run-004完整矩阵](fixtures/planning-material-matrix-2026-10-06/r4-preflight/run-004/results.json) **66 PASS/4 FAIL/0 GAP/0未执行**；[run-005诊断](fixtures/planning-material-matrix-2026-10-06/r4-preflight/run-005/results.json)保存解析相等、两个完整请求SHA、键序差异和原生检查点/RPC序列，6项 **2 PASS/4 FAIL**，四个FAIL同根因，未使用skip/xfail。lost不重提交、已知terminal error不刷新Preparation重试两个保护场景通过。正常异步路径尚未到B/Truth，不能声称四阶段恢复验收已通过。

[全量JUnit](fixtures/planning-material-matrix-2026-10-06/r4-preflight/async-lifecycle-junit.xml) **801 PASS/4 FAIL/5既有skip，54.98秒**，4个新增FAIL全部属于同一异步恢复根因；115技能/compileall/diff检查通过。生产source0907/HEAD99b3和257旧现场、25fixture前后不变。[Astra只读复核](fixtures/planning-material-matrix-2026-10-06/r4-preflight/async-preflight-astra-review.txt)为STOP；后续最小方案见[Task §13.1](../tasks/planning-material-boundary-matrix-2026-10-06.md#131-异步前置回归发现生产缺陷2026-10-07stop)。本轮未修改生产、重启服务、修写正式证据或调用外部模型；新调用/费用均0，旧费用不清零。

[结构化汇报](fixtures/planning-material-matrix-2026-10-06/r4-preflight/async-preflight-summary.json)：新真实Planning **NOT_EXECUTED**，软件前置 **FAIL**，R4停止，READY_FOR_MATERIAL_SMOKE=NO。历史raw-stream丢失例外及旧FAIL保留。受保护本机原批目录下`async-preflight`仅新增本次诊断归档，原正式运行成绩未覆盖。

## R4 固定与评测预检（2026-10-07，以下为首次批次历史）

固定 commit `99b3ca836f7c50f5ecfbea46661f91d4c40c808b`，202文件生产SHA `0907c35cf4ee98254ac0a598f924d7b757b4aaf29cc24d1ac1d3f234d5e65217`。提交67个获批文件，无push、无其他工作树覆盖。既有LaunchAgent加载Web71192/Gateway71182，健康200、runtime2026.9.4，实时8旧Owner无有效操作，pending/submitting/release=0、Gatewayactive/queued/running/lost/audit=0。实际进程启动路径/cwd/新PID及启动前后源码指纹证明加载；未声称存在进程内部SHA端点。

新增raw-stream事故：备份错用不存在的`/tmp/easel-raw-stream.jsonl`，实际`~/.openclaw-easel/easel-raw-stream.jsonl`被wrapper第16行清空。重启前原始大小/摘要未知，不能断言原本为空；257份正式Creation/Attempt现场及历史fixture未变，不等于全部日志无损。旧2026-10-06备份早于最新失败，五个相关SQLite会话395条脱敏事件仅作补充。用户明确接受本次保留例外，不恢复旧Creation，四轮历史FAIL及先前事故保留。当前实际流路径0字节已经备份作事故后新基线；不倒算原始流保护PASS。

本轮真实费用范围：已购文字套餐额度，禁止现金/API余额/超额/付费回退；用户指示直接沿用当前配置。同一当前Key调用官方`https://www.minimax.cn/v1/token_plan/remains`只读成功，当前5小时100%、周99%，MiniMax-M3及fallbacks=[]。套餐余量每阶段检查，未知或低于25%停止；并非原子账号消费锁，实际账单未知。不迁移模型，不复用旧图片/旁白¥10授权。阶段提交不是单次底层模型HTTP请求：一次Agent执行可能含多次工具/模型交互，后续分别记录账本身份与可取用量。

冻结[16正常主题与独立语义预期](../../tests/fixtures/planning-eval-r4-2026-10-07/samples.json)，8development/8held-out，各2次；样本SHA `48a1e8bdf4bf1d61c68fa3a47916c001165b8c2ffbce79547c44ed74c37cf43a`。32个正常确认Creation及独立proposal/script摘要保存在隔离本机roster。此时正常确认不包含实时模型，不能计作32次真实Eval通过。

评测器执行正式内部链，到原生Supply import之前由AST固定trace截断；真实persist之后load复验且Truth必须PASSED。每次to_thread重装trace，覆盖线程池重入。隔离validator子进程只改变Creation根路由，运行原始只读合同校验，不改schema/语义。实际HEAD/生产SHA/工具SHA/样本SHA和批次级旧现场基线固定；完成后任一变化/检查异常/Supply或状态违规强制FAIL；第n条前0..n-1每条合同及独立语义审核必须PASS。该隔离是本次原生进程调用链保护，不是远端Agent操作系统沙箱。

软件装配证据：同一执行器[r4-preflight/run-002](fixtures/planning-material-matrix-2026-10-06/r4-preflight/run-002/reconciliation.json)64PASS、源码/257旧现场/25fixture不变；[R4针对性JUnit](fixtures/planning-material-matrix-2026-10-06/r4-preflight/assembly-final-junit.xml)12PASS，含真实validator子进程及跳前序/指纹漂移/未知与不足额度/最后Truth后现场变化强制FAIL；[具名完整回归](fixtures/planning-material-matrix-2026-10-06/r4-preflight/full-pytest.txt)793PASS/5既有环境skip（运行后新增的6项工具保护由上述针对性验证另列）。Astra最终CONTINUE，无新增必要修订，仅允许受限R4；不授权Smoke/E2E。

首条真实运行中，尚无评测通过结论。本机原始运行记录、授权、配额、版本、事故、roster和工具基线位于受保护的`~/Library/Application Support/Easel/acceptance/planning-eval-r4-2026-10-07`；不进入Git，不保存凭证。所有真实失败、unknown及独立语义判定后续原样登记。


### R4 实际运行结果：评测工具 FAIL，冻结批次停止

第0项/第1次独立运行，Creation `cr_ba74da6edaa94941b0d9f84d2ee9a6ce`，真实Preparation原run `easel-073b51763c8a4350a2494992e78c6044`。初次执行原生Owner返回`execution_uncertain`/pending；第二次只调用`observe_agent`核对原run，返回`observing_execution`且仍pending。冻结runner只将`execution_uncertain`/`observation_failed`识别为非终态，遗漏`observing_execution`，错误进入FAIL分支。这是**EVAL_TOOL_OBSERVATION_STATE**，不是已证实的生产Planning合同失败。

保留runner实际FAIL、两次调用完整快照和诊断事故，不改冻结工具、不人工改正式证据、不创建新request救场、不运行第1项或后续主题。仅正式reconcile原请求至终态：`ok`、`runtime_release=released`；模型自然完成四份准备文件，原生只读validate PASS，无Attempt、无A/B/Truth。完整68事件会话和实际重启后raw-stream脱敏归档；新日志归档不冒充恢复旧日志。截止终态Gateway657条全终态、active/queued/running/lost/audit=0；257旧现场及固定生产、评测工具指纹未变。

[脱敏最终报告](fixtures/planning-material-matrix-2026-10-06/r4-preflight/actual-run-summary.json)分别记录：32项冻结/1项开始/Planning执行0/31项未执行；INITIAL_SUCCESS与FINAL_CONTRACT_SUCCESS为0/32已验证，不能解释为32次Planning都失败；held-out0/16；语义覆盖未评估；repair0；状态越界0；正式Supply/Provider/生成/TTS/Build0；重复付费提交0；ENGINEERING_INTERVENTION=0（首次真实提交后没有代码或证据救场）。

Preparation durable run约123.408秒，模型会话跨度119.56秒；两个客户端Owner调用总3.566秒不等同模型墙钟。实际1个Gateway Agent原run，16个MiniMax-M3 assistant响应、32工具调用（exec/read/write，20exec，最终原生validate命令1次）；A/B/Truth0。工具指令审计未见供给、采购、生成、TTS、Build执行入口。单次Agent提交不等于单次底层模型调用；Provider元数据token及cost全0，没有可用实际账单，**不能宣称免费**。只读套餐5小时100→99%、周99→99%，是共享账号用量差值，不能精确归因本次现金成本。

本轮 `PLANNING_EVAL=FAIL（评测器）`，`READY_FOR_MATERIAL_SMOKE=NO`。该运行未检验Planning在真实输出下的合同或语义稳定性，不能据此归咎模型或宣告R0–R3失败。后续需要新冻结工具和独立批次；本批不改分、不恢复计分。


## R4 新固定版本与独立批次（2026-10-07，运行中）

旧99b3版本两类失败不改。后续独立软件修复仅三处稳定JSON序列化，同一矩阵run-00670PASS，全量805PASS/5既有skip（58.20秒）；115技能、compileall、diff与AstraCONTINUE。未迁移旧非规范pending，未恢复失败作品或放宽身份/语义保护。

新commit `a7f7ccfea07fb7ebb64534267e22959fe948ef72`、production SHA `327842e4e249481f75ffc934c973c1621807e7cc7e3073ab01b1b82b7053a636` 已固定，无push。新Web77120/Gateway77118、10:28:16启动及既有可执行/cwd与固定SHA对应；无进程内SHA端点，依据为新PID/启动时间/固定源码。8旧Owner有效操作0、任务active/lost/audit0、账本pending/submitting/runtime release0。257旧现场和25fixture仍不变。Gateway停后actual raw-stream 229259字节/SHA备份核验后启动；一次bootstrap瞬态失败，经确认service缺失后同plist重试成功。没有复制credential配置，未扩大服务范围。

只用原授权已购文字套餐，官方同Key余量99%/99%，无fallback。原预先冻结16主题/8dev+8held-out和独立oracle保持SHA；32个全新正常确认Creation在batch02隔离根冻结，不复用旧Plan/Attempt/Need/报告。工具指纹、源码、样本和历史现场均固定；正在第0项真实Preparation，不能认领32次Planning或Smoke成功。完整新批记录在受保护本机目录，后续结果继续补本验收入口。


### R4 batch02实际结果：FAIL / STOP

第0项《桌上的两张纸》已完成正常Preparation、A及唯一repair，三个原runok/released；正式消费者拒绝，B/Truth未启动。完整202.975秒，Planning首A至消费者拒绝约97秒；原Preparation102.624秒、A64.070秒、repair22.496秒。1项FAIL、31项未执行，0/1已执行项合同成功；不能解释为32项全部执行失败，held-out0/16。

初始A.policy五个值为bool，违反dict[str,str]；未放宽Schema。真实repair请求只给SEMANTIC_PLAN.json basename，没有Attempt workspace或绝对目标。独立repair会话一次write到`~/.openclaw-easel/workspace/SEMANTIC_PLAN.json`，正式Attempt/planning原文件未修，记录A.raw==repair.raw。误写文件已把policy改为string，但未正式消费，不能称repair成功。错误A SHA `ea51bf200adaaf4b7c844d6d0a69605603ac8a7cab02defcce47961ed169e460`，误写原件SHA `d50d97b9f59d3c24425d815cfe24085c5a28bfba6a1cbc3c1ca43bb789a549f4`；原件受保护归档、未移动进正式Attempt或人工补证。

[Astra](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch02-astra-review.txt)核实生产repair输出目标合同缺口，以及fixture从闭包或Creation补输出root造成漏测；DECISION=STOP。MODEL_OUTPUT与STRUCTURAL_CONTRACT分别记录；后续最小修复/回归见Task§13.3。本次真实调用后未修改固定生产/工具，工程介入0；STATE_VIOLATIONS=1（repair输出范围越界），workflow越级0，Supply/Provider/生成/TTS/Build0。

实际提交Prep/A/repair各1，19assistant响应、29工具（15exec/8read/6write）、17observe_agent及17pending检查点，无重复付费提交。5小时套餐99→98%、周99→99%，账号共享余量，实际账单未知，provider metadata0不能算免费。Gatewayactive/lost/audit0，三个原run释放完成；257旧现场/25fixture/源码/工具/冻结正文保持。本次范围不能证明错误输出路径过去不存在，不认领全Gateway workspace无损。

[完整结构化报告](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch02-actual-run-summary.json)。正式Plan/requirements未成立，语义覆盖未验证，READY_FOR_MATERIAL_SMOKE=NO。完整运行、请求、原稿、错误路径原件、SHA、脱敏会话与raw-stream存于受保护本机batch02目录，旧批FAIL和费用原件保留。本批不继续下一项，不回填计分。


## R4 batch03真实FAIL及repair路径软件证据（2026-10-07）

§13.4独立软件：修前run-007原生异步A/B repair 6PASS/2FAIL，修后run-008完整72PASS；全量810PASS/5既有skip（59.88秒）、115技能/compileall/diff通过、AstraCONTINUE。固定commit63da1b00/source61b6a75e并安全加载；原始raw精确备份，257旧现场和25fixture保持。

另起32个全新Creation，实际第0项batch03在205.748秒后FAIL/STOP，后31项未执行。Prep/A/repair各1，路径绑定真实起效；policy类型修复后仍遇约束列表标量filter错误及unknown continuity引用，B/Truth未执行。最终合同0/1实际执行项；held-out0/16；不能用离线诊断冒充正式成功或完整语义评分。3run均ok/released，24模型响应、25工具、17原run观察；Supply/Provider/生成/TTS/Build=0、工程介入0、状态越界0。套餐5小时98→97%/周99→98%，实际费用UNKNOWN。固定版本、工具、SCRIPT、旧批/旧现场/历史fixture未变。失败后只读归档并AstraSTOP，不继续本批、不手改产物、不给Smoke放行。

完整结构化字段：[batch03-actual-run-summary.json](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch03-actual-run-summary.json)；[Astra STOP](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch03-astra-review.txt)。受保护本地记录目录 `~/Library/Application Support/Easel/acceptance/planning-eval-r4-2026-10-07-batch03` 包含运行/请求/调用/模型会话/原A与repair/源码SHA/备份原日志及脱敏流。后续范围由同一Task §13.5统一规划；本次合同修改尚未实施。所有历史FAIL不变，真实Planning Eval32项门槛仍未达成。

## R4 batch04 软件固定与服务加载（2026-10-07）

沿用原Task §13.6/13.7，固定commit `b819d2877c65d2c10836d076415a0cc47690377b` / production SHA `79e580c163c77cafc47d4056c910e1aaf5bcc49419be31e78497d08588a54825`；最终run-013 80 PASS/0 FAIL/0 GAP/0未执行，全量818 passed/5既有skip/62.31秒，115技能/compileall/diff通过，Astra CONTINUE，合法五模态Plan序列化无变化。没有push，其他用户工作树保留。

实时旧Owner有效操作0、unknown/pending/submitting/release pending0、Gateway active/lost/audit0。实际raw-stream在两服务停止后备份52235字节，SHA `385f6ec4f9b4624b2e8d88b6779e576cbc721eeb94f6b0ee84ef22c4af4f7b83` 完全核验；11:20:21新Gateway PID86938/Web86940启动，HTTP200，初次检查未就绪后自然稳定，无重复reload。加载身份由新PID/时间/可执行文件/cwd/固定磁盘源码证明，现系统没有进程内SHA端点，不扩大声明。257旧现场/29fixture/batch02/03原件不变。预提交记录通用脱敏遮蔽的secrets.py单项hash用完整源码SHA核验；两份历史授权原件与保留副本逐字节一致，未改原件或基线。

同Key官方文字套餐余量97%/98%、MiniMax-M3无fallback，沿用用户明确套餐/direct-use授权；实际账单未知。受保护batch04目录保存预提交/JUnit/Astra/实时预检/停服操作/日志备份/loaded/32个新Creation roster/源码与工具基线。原16主题及独立oracle不变，首次实际调用前尚无新模型成绩，Supply/Provider/生成/TTS/Build=0。所有旧FAIL仍保留；本节不认领R4或Smoke成功。

## R4 batch04 实际首项：结构合同PASS、独立语义FAIL / STOP（2026-10-07）

固定b819d287/source79e580，以32新正常确认Creation执行第0项《桌上的两张纸》。四原run Preparation/A/B0/Truth全部ok/released，无repair；正式Plan/Requirements与PASSED Truth持久重载一致，评测在原生Supply import前停止。Native Owner仍preparing/next prepare，不人工写MATERIAL_SUPPLY状态，也未真实执行Supply。冻结正文、两张白纸required、静态image/9:16/静音均保留。

独立语义FAIL并立即停止后31项：正式Requirements将“由后期叠加。”以及被引号/标点切碎的SCRIPT引用列为视觉required，违背确认SCENES的后期义务。结构覆盖并不证明kind正确。Astra STOP；primary_visual分类合法，部分无人/构图有Prep/Mode来源，不把这些一律算无来源新增。显式preferred与description required重复自然光等另记强度风险，FAIL不依赖争议项。Truth只证明正文创作表达，不替代Material分类。

合同首次及最终1/1执行项（1/32计划项），语义总体0/1，held-out0/16未执行；1语义FAIL/31未执行。墙钟257.450秒、Planning含Truth至切点173.171秒；4真实提交、36assistant/32工具、21原请求观察，7callback含3原身份缓存重入，重复实际提交0。repair/补证/报告修复0、Supply/Provider/生成/TTS/Build0、状态越界0、工程介入0。文字套餐5小时97→96%、周98→98%，共享比例与Gateway零usage/cost不等于实际费用，账单未知。

收尾Gateway active/lost/taskAudit0、四run全部released、各批无pending/submitting/release pending。257旧正式现场/29fixture/batch02的134原文件/batch03的136原文件/source/tool/HEAD/samples/SCRIPT未变；评分仅更新诊断记录，全部正式文件hash不变。保存受保护原日志、脱敏全会话、原始产物/身份/时间、独立oracle评分、Astra及固定版本；不修写、救场或恢复本批，不认领Smoke。下一步设计见原Task §13.8，仅离线独立软件规划，当前生产与真实模型停止。

[结构化完整指标](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch04-actual-run-summary.json)、[独立评分](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch04-independent-semantic-review.json)、[Astra STOP](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch04-astra-review.txt)。

## R4 引用关系独立软件验收（2026-10-07）

按Task§13.9/13.10完成@2/@8引用完整性及B实际确认依据绑定，显式兼容有效旧@1/@7，Material合同/额度不变。修前run-015 2 PASS/4 FAIL；完整run-018 87 PASS/1 FAIL的合法副本回归保留，实际持久化输入/已核验保存文件分别校验后最终run-019 **88 PASS/0 FAIL/0 GAP/0未执行**。全量826 PASS/5既有skip（59.06秒）、115技能/compileall/diff通过，AstraCONTINUE。源码SHA `0657a8c27e3cf6ef2ace05ed8a8c00c15cb7604ff28dcd1d3ac28863e7fcfa48`；257旧正式现场/29原fixture未改，新增14原件后43前后不变。

旧真实错误kind与新形状错误kind都保留结构PASS/独立语义FAIL证据；离线正确kind不是模型成绩。软件真实调用及下游0，batch04全部FAIL不变。受保护batch05目录仅保存软件记录/授权/原件SHA，尚未真实运行；后续固定commit/安全加载/32新Creation不覆盖本结论。

## R4 batch05 固定版本/安全加载（2026-10-07）

固定commit `59bd7d857c6d955761a0d7fc217c713477b02762` / production SHA `0657a8c27e3cf6ef2ace05ed8a8c00c15cb7604ff28dcd1d3ac28863e7fcfa48`，仅提交20获批软件/原件/Task文件，无凭证或运行产物，无push，其余用户工作树保留。run-019 88 PASS/全量826 PASS及Astra CONTINUE固定。

实时8旧Owner有效操作0，各批unknown/pending/submitting/release待办0，Gateway active/lost/audit0，同Key套餐96%/98%且无fallback。全部4旧批原文件SHA/257正式现场/43fixture一致。Web/Gateway11:59:15新PID94376/94374加载，HTTP200/空闲；停服后实际raw精确备份1,092,870字节，SHA `fdfe9f65ef740c4756981f6dffb21a31927475220cb90c2b704d55867b255933`已核验，无新增日志丢失。进程内SHA端点仍无，仅由新PID/时间/执行文件/cwd及固定源码佐证。

新批原16主题/oracle不改，独立32正常Creation与新请求身份冻结，已开始第0项；尚无正式合同及独立语义成绩。每项双重通过后才下项，实际Supply/Provider/生成/TTS/Build禁止，历史FAIL不改，Smoke=NO。[加载摘要](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch05-release-loaded.json)。

## R4 batch05 实际首项：合同PASS、叙事审核目标语义FAIL / STOP（2026-10-07）

固定59bd7d85/source0657a8c27e3cf6ef2ace05ed8a8c00c15cb7604ff28dcd1d3ac28863e7fcfa48，32新Creation，实际第0项Prep/A/B/Truth四runok/released，无repair，正式持久重载PASS，未进入Supply。此前引用和正文后期职责正确，明确两张白纸required/image/silent/SCRIPT保留。但“不要替读者补完两张纸的来由。”成为asset required：相同素材不变，仅作者叙事改变即可违反。来源存在却交给错误审核对象，Main独立核定FAIL、Astra STOP。无人物/文字有上游硬来源，偏好重复不单独判FAIL。

1语义FAIL/31未执行，held-out0/16；正式合同初始/最终1/1执行项（1/32计划），语义0/1；墙钟277.094秒、Planning含Truth193.519秒。4原提交/33模型响应/41工具/23原请求观察，7callback含3缓存恢复，实际重复提交0。NORMALIZE/repair/report repair/工程介入/状态越界/正式Supply及全部下游0。文字套餐96→95%/周98→98%，实际费用未知。

257旧正式现场/43fixture/4旧批原件、源码/工具/样本/SCRIPT保持；独立评分不修改正式产物。无pending/submitting/release待办，Gatewayactive/lost/audit0；完整原日志及脱敏会话、身份、正式文件SHA、独立oracle反事实核定保留受保护batch05目录。[完整指标](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch05-actual-run-summary.json)、[独立评分](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch05-independent-semantic-review.json)、[Astra STOP](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch05-astra-review.txt)。按Task§13.11只把真实失败转为后续独立治理证据；不继续本批、不手改kind、不认领Smoke。

## R4 batch06 软件固定及安全加载（2026-10-07）

审核对象说明软件固定commit `0b176a2a8fa30b01c652aa044f176feb93c2639e` / production SHA `f01fe3317b4aa223caddea08ee0ee86cf5d3347944dc9698fd997c7a00e66005`，仅提交20获批源码/测试/fixture/Task文件，无凭证运行产物或push，其余用户工作树保留。最终run-023 96 PASS/0 FAIL/0 GAP/0未执行，全量834 PASS/5既有skip（61.09秒）、115技能/compileall/diff及AstraCONTINUE。

实时8旧Owner有效操作0，各批unknown/pending/submitting/release待办0，Gateway active/lost/audit0；同Key文字套餐95%/98%，无fallback，实际账单未知。257旧正式现场/59fixture及全部5旧批原文件SHA一致。实际raw-stream停服后精确备份2,328,086字节，SHA `4273588d9aaf2b9d87b83095f8db95fb946fb1ed563279fc7acbc3ae42e16853`核验；12:19:50 Web/Gateway以新PID96725/96723加载，HTTP200/Gateway空闲。无进程内SHA端点，加载证据限定为新PID/时间/可执行文件/cwd及固定源码。

原16主题和独立oracle不改，新32正常确认Creation及请求身份隔离。第0项开始实际Prep/A/B/Truth；每项正式合同+独立语义均通过才推进下项。禁止实际Supply/Provider/生成/TTS/Build，全部旧FAIL保留，不认领Smoke。[加载摘要](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch06-release-loaded.json)。

## R4 batch06：素材属性与后期用途混合分类仍语义FAIL（2026-10-07，STOP）

固定0b176a2a/sourcef01fe331，以32个全新正常Creation执行第0项。Preparation/A/一次共享A repair/B0/Truth五原run全部ok/released；初始一个query超过100字符，既有Schema已明确maxLength100，系统仅修查询且有效语义不变，不存在查询长度Schema缺口。正式合同/Truth及持久重载PASS，原生Supply import前停止。

独立Main审核与Astra STOP：“整体构图留出较充足的负空间以便后期叠加一行文字;”被整句编为postproduction。源图构图是素材可观察属性，“以便后期叠加”是用途修饰，不能将前者整体变成编辑操作。本次显式preferred_visual_details另有generous negative space around the two sheets，且无确认/Preparation硬负空间来源，因此应沿该来源为preference；确实无法无损判断则unresolved。明确负空间偏好已保留，不能报告遗漏、required降级或升级；但另处正确preference不能抵消错误kind。前次作者经历义务本次正确postproduction，证明改善而非整个语义通过。

原两张白纸required/image/9:16/silent/SCRIPT保留。本批1项语义FAIL、31未执行、held-out0/16；初始无需repair合同0/1，最终正式合同1/1执行项（1/32计划），独立语义0/1。墙钟211.901秒、Planning含Truth150.381秒；5原提交/36assistant/34工具/17原请求pending观察，9应用callback含4缓存原请求重入，重复提交0。NORMALIZE/report repair/补证/实际Supply/Provider/生成/TTS/Build/状态越界/工程介入0。共享套餐5小时95→94%、周98→98%，实际账单未知。

评分仅诊断，不修改正式Plan/Requirements/Truth；固定HEAD/source/tool/sample/SCRIPT、257旧正式现场/59fixture和全部5旧批原件SHA保持。五原run全部释放，各批pending/submitting/release待办0，Gatewayactive/lost/audit0。完整原始日志与脱敏会话、请求身份、原件/独立反事实评分和固定版本保存受保护batch06目录。本批FAIL/STOP永久保留，不追加repair、不启动后31项、不恢复计分，Smoke=NO。

后续独立治理先区分素材属性主谓与制作目的/用途修饰，并同时保护纯后期操作、作者义务、明确hard/soft来源及源视频动作；不按“后期/负空间”等关键词决定kind，不增加修复额度或生产语义Gate。新设计须保留@1/@2/@3原输入及缓存身份，前置Astra复核、实际失败回放和完整不回归后才能固定另一版本、新32项R4；本节不认领修复或模型通过。

[完整指标](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch06-actual-run-summary.json)、[独立评分](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch06-independent-semantic-review.json)、[Astra STOP](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch06-astra-review.txt)。

## R4 主体条件与用途关系软件验收完成（2026-10-07，未执行新真实模型）

按§13.15及Astra前置CONTINUE完成compiler@4/target@2：实际任务携带主谓/用途、审核对象、强度/kind关系规则，A/B及共享repair一致使用。旧@3完整原target@1独立保存，原真实B payload/digest/checkpoint/复制精确恢复；@1/@2及standalone不变，旧pending不新派发或刷新额度。源属性不因用途整体变后期，独立混合义务无法无损分类仍unresolved，无词面算法、新模型Gate/输出字段/调用/额度，Material V1.3职责保持。

用途前置软源属性、明确hard主体＋用途、纯后期叠字、后期裁切留白、源动作＋用途及作者事实义务对照均通过正式内部编译。真实旧和新政策错误kind仍结构PASS/独立语义FAIL，正确替身仅证明合同可表达，不认领真实模型改善。

最终同一入口run-027 **103 PASS/0 FAIL/0 GAP/0未执行**，全量 **841 PASS/5既有skip**（60.44秒）、115技能/compileall/diff通过，Astra实际diffCONTINUE，无新增必要修订。首个全量834PASS/5skip/1ERROR因新增helper遗漏parametrize，原JUnit保留，仅补测试参数化后完整重跑；run018/024/025及测试缺陷不删除。257旧正式现场/原59fixture未改，新增18后77fixture前后保持，六旧批完整原件保存。生产SHA `71e5ecbbafdfd7104b835a5b6b2a3071a2132e291d31d5134dab9281547e99e4`，软件真实调用及Supply下游0。

软件冻结条件成立，后续仅按已授权范围窄提交、本轮实际日志停服精确备份、安全加载/实时空闲/套餐预检后，用原16主题及独立oracle另建32个全新正常Creation进行R4；旧batch06及全部历史FAIL不恢复不倒算。软件通过不放行Smoke，真实成绩另记唯一验收。

## R4 batch07 固定版本及安全加载（2026-10-07，真实结果未定）

§13.15/13.16软件固定commit7685953c72925b195aa7e882996aca076a2151bb / source71e5ecbbafdfd7104b835a5b6b2a3071a2132e291d31d5134dab9281547e99e4，仅22获批软件/fixture/Task文件，凭证/运行产物0、无push，用户其余工作树保留。run027103矩阵PASS、841全量PASS/5既有skip、115技能/compileall/diff及AstraCONTINUE。

实时8旧Owner有效操作0，unknown/pending/submitting/release待办0，Gatewayactive/lost/audit0；同Key文字套餐94%/98%，无fallback，实际账单未知。257旧正式现场/77fixture及全部六旧批原件SHA一致。实际raw-stream停服后精确备份172336字节、SHA2047330750c5f7c2bfe05910d0aec41c4f6906422aaddd8db8c22f8a95b2b773核验，12:57:24 Web/Gateway新PID99217/99215安全加载，HTTP200/Gateway空闲；无进程内SHA端点，依据为新PID/时间/执行文件/cwd及固定源。

原16主题及独立oracle保持，新32正常确认Creation冻结隔离，请求身份独立，首次真实Prep/A/B/Truth开始；尚无新成绩。每项正式合同与独立语义均PASS才继续；禁止实际Supply/Provider/生成/TTS/Build，所有旧FAIL不恢复不倒算，Smoke=NO。[加载证据](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch07-release-loaded.json)。

### batch07 第0项：正式与独立语义双PASS（尚仅1/32）

首项《桌上的两张纸》正常Prep/A/B0/Truth四原runok/released，无repair。两张白纸/static/image/9:16/silent/SCRIPT保持；引用正文、字幕叠加、作者表达function为postproduction，明确光线/色调/负空间及后期用途为preference，没有错误hard源义务。Main逐项阅读原oracle、Creator/Director/Preparation、实际A与正式clauses独立判PASS；没有自动按词面评分或手改产物。完整正式文件SHA审核前后不变。

179.898秒、Planning/Truth109.883秒，4实际提交/20assistant/29工具/15原请求pending观察/3缓存原身份重入，无重复提交。套餐94→93%/周98→98%，实际账单未知。Supply下游/状态越界/工程介入0，源码工具/257旧现场/77fixture及六旧批原件保持。当前1/32、held-out0/16，未达到发布门槛，Smoke=NO；第1项同主题第二次独立新Creation进行中。[单项记录](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch07-run00-summary.json)。

## R4 batch07：前两项双PASS，第3项分类枚举与repair输出结构FAIL（2026-10-07，STOP）

固定7685953c/source71e5ecbb的新32项：第0/1项《桌上的两张纸》正式合同与独立语义均PASS，无repair，正式原件未改；第1项四相同scope Need的冗余风险保留，V1.3可一Asset多Need，不能事后加“一Need”评分。第2项《给绿植留一点时间》正常Prep/A/B0/唯一B repair四原runok/released，但正式消费者拒绝，Truth未执行；全部立即STOP，后29未执行、held-out0/16。

初始B unit8.kind为`narrative_or_postproduction`，复制了review_target的说明标签，合法四kind不包含该值。程序已拥有正确原文映射，却把非法kind与引用越界合并报“要求引用不属于冻结原文”，repair随后推理不存在的引用问题。实际初B只有required JSON例子；repair response_schema只是“same schema/IDs as original batch”说明字符串。真实repair返回batch_id/compiler_policy/review_target/responses/notes输入式wrapper且保留非法kind，_merge_repaired严格拒绝；不自动映射标签、不剥wrapper或再修。Astra STOP：MODEL_OUTPUT违规＋STRUCTURAL_CONTRACT输出指导/错误诊断缺口，严格拒绝本身正确；误诊干扰修复有支持证据但不认领唯一因果。

3项已执行/29未执行，初始及最终正式合同2/3（计划2/32）；仅两项可正式语义评分，均PASS，失败项无正式Requirements，语义覆盖UNVERIFIED。共享repair1、正式成功0/1、NORMALIZE/report repair0。完成项累计墙钟616.810秒、Planning含Truth/失败边界401.139秒；失败项228.669秒。12实际提交/77assistant/104工具/51原请求观察，21应用callback含9缓存重入，无重复实际提交。Supply/Provider/生成/TTS/Build/状态越界/工程介入0。共享文字套餐94→91%、周98→98%，实际账单UNKNOWN。

257旧正式现场/77fixture/六旧批完整原件及HEAD/source/tool/原16主题/SCRIPT保持。所有12原run释放，所有批无pending/submitting/release待办、Gatewayactive/lost/audit0；完整原日志/脱敏会话/请求身份/原A/B/repair/现场hash保存在batch07受保护根。评分不修改正式产物；失败项无正式Plan/Requirements/Truth，不虚构语义成绩。A的preferred描述夹连续源动作仅记录后续风险，不追加正式评分。本批及历史FAIL永久保留，Smoke=NO，不继续计分或恢复。

[完整指标](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch07-actual-run-summary.json)、[失败边界核定](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch07-independent-failed-review.json)、[Astra STOP](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch07-astra-review.txt)。

## R4 B输出合同软件验收 B输出合同软件验收完成（2026-10-07，未执行新真实评测）

§13.18及Astra前置/实际diff CONTINUE后完成compiler@5：初始B与唯一B repair共用程序构造的Draft2020-12逐单元输出Schema，固定排序四kind、整数id及完整按序覆盖、所属Need的显式preference ID/null；repair精确affected indexes，顶层仅batches。运行时独立严格核验wrapper/ID/kind/pref，非法kind先报告unit.<id>.kind，不再误报冻结来源，错误wrapper与index分别报告。未放宽消费者、自动映射说明标签或剥wrapper，无新Gate/模型调用/额度/Domain重构。@4显式保留原target@2及无Schema批次digest，@1–3保持；旧pending不重派、不迁移。

新增batch07实际事故原件、请求与独立Expected，以及另存run00合法@4 checkpoint，共13fixture；失败项partial snapshot不冒充正式Plan。修前run028因测试误用Python严格反序列化7FAIL，原记录保留；仅改为JSON反序列化后run029 **2PASS/5FAIL**，准确暴露诊断/Schema/身份缺口，生产不变。修后完整run030110PASS；补唯一B repair显式Schema说明后最终run031 **110PASS/0FAIL/0GAP/0未执行**。全量 **848PASS/5既有skip**（62.79秒），115技能、compileall、diff PASS。既有原生异步Owner accepted/pending/原run释放/Truth/Supply前切点及多批保护执行，外部B/repair替身从实际提交Schema与绝对path获得形状/ID，只有固定语义答案；不认领真实模型改善。

生产SHA `b64681a0c8b650d509824e4cb376fc6dfb05d0c0fc6a5d3a8850a812f1f4e548`，257旧正式现场/90fixture保持；batch07及全部历史FAIL不改，软件外部模型/Supply下游0。Astra实际diff无需新增修订，软件冻结条件满足。下一步按既有授权窄提交、安全加载/套餐/实时空闲检查，在原16主题/oracle另建全新32项batch08；不能续跑或重计batch07，不放行Smoke。

## R4 batch08 固定版本与安全加载（2026-10-07，真实结果未定）

§13.18/13.19固定commit4614db7142ab6e189dde49fefd7356eafbb2cf74/sourceb64681a0c8b650d509824e4cb376fc6dfb05d0c0fc6a5d3a8850a812f1f4e548，仅17获批源码/测试/fixture/Task文件，凭证/运行产物0，无push，用户其余工作树保留。run031110矩阵PASS/848全量PASS/5既有skip、115技能/compileall/diff及AstraCONTINUE。

实时8旧Owner有效操作0，各批unknown/pending/submitting/release待办0，Gatewayactive/lost/audit0；同Key文字套餐91%/98%，无fallback，实际账单UNKNOWN。257旧正式现场/90fixture及全部七旧批原件SHA保持。实际raw-stream停服后精确备份1,150,865字节、SHAb3a4059cfdc3480a1386d4c7c49c940c99a33db82d076836c2504c8d9543639d核验，13:25:39 Web/Gateway新PID2814/2812安全加载，HTTP200/Gateway空闲。无进程内SHA端点，证据仍为新PID/时间/执行文件/cwd与固定源。

原16主题和独立oracle不变，冻结32全新独立正常确认Creation，真实成绩尚未产生；逐项实际Prep/A/B/Truth与独立语义评分，正式双PASS才继续。实际Supply/Provider/生成/TTS/Build禁止，全部历史FAIL保留，Smoke=NO。[加载记录](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch08-release-loaded.json)。

## R4 batch08 batch08：完整Schema实际生效，持续unresolved导致正式FAIL（2026-10-07，STOP）

固定4614db71/sourceb64681a0的新32项首项《桌上的两张纸》正常Preparation/A/B0/唯一B repair四原runok/released。初B与repair均通过实际完整输出Schema，四kind/wrapper/ID正常，repair与初B分类完全相同。unit5整个function为“Carries the entire 0–15 second visual in a single static frame; the two blank papers on the desk embody the unspoken subject, while the spoken line is layered on top in post-production by the SCENES / TREATMENT workflow.” 两次均unresolved，正式消费者正确拒绝；Truth未执行，无正式Plan/Requirements。

独立Main及Astra STOP本批/MODIFY后续定性：整段主要是成片使用、表达及后期操作，静态两张白纸已由description/image保留，整段postproduction为合理可表达对照。“严格拒绝unresolved正确”不等于“unresolved语义判断正确”。function强制整段确是实现事实，但本例不能证明它导致表达容量不足；不能只复制模型mixed理由作oracle，不能拆段后将时长使用或表达用途硬化。@5输出合同修复本次真实工作，仍不足以保证自然语言分类正确。

本批1项FAIL/31未执行、held-out0/16；初始输出Schema1/1合法，初始/最终可用正式合同0/1（计划0/32），repair0/1、无变化修复1；正式语义/required覆盖未验证。耗时218.823秒，失败Planning136.344秒；4原提交/25assistant/41工具/18原请求pending观察，7应用callback含3缓存原身份重入，无重复实际提交。Supply/Provider/生成/TTS/Build/状态越界/工程介入0。仅已购文字套餐91→90%、周98→98%，实际账单UNKNOWN。

源码/工具/原16主题/SCRIPT、257旧正式现场/90fixture及七旧批完整原件保持。四原run释放，各批pending/submitting/release待办0、Gatewayactive/lost/audit0，实际raw精确归档/脱敏会话/请求/原件SHA保存batch08受保护根。未修改正式产物、未追加repair、不继续或重计本批。全部历史FAIL保留，Smoke=NO。[指标](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch08-actual-run-summary.json)、[独立失败核定](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch08-independent-failed-review.json)、[Astra](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch08-astra-review.txt)。

## R4 成片使用与源条件软件验收 成片使用与源条件软件验收完成（2026-10-07，未执行新真实评测）

§13.21经Astra前置和实际diff CONTINUE，compiler@6仍units@8，不修改function粒度。target@3新增审核对象反事实规则：只辅助判断义务约束谁，不按后期可编辑性分类；原图两纸条件在成片裁掉一张后仍约束原素材，使用方式/象征表达复述主体不自动创建或擦除源义务。A/B/共享repair一致收到新说明，无关键词/字段算法、额外字段/Gate/调用/repair额度，Material V1.3语义保持。

显式固定@4/@5原target@2及@5完整output_schema能力；@1–5原映射、批次身份和旧pending保护保持。batch08十份原件/独立Expected脱敏保存，partial snapshot不冒充正式Plan。实际unresolved在新旧政策都正式拒绝，整段postproduction仅独立合理对照，不恢复历史评分；12组源/使用/裁剪/源动作/印刷字/软偏好及真不可分混合保护通过。实际@5 B payload精确复算；合法@5checkpoint由真实内部模块离线派生并明确非真实历史PASS。

修前run0323PASS/2FAIL，暴露新任务传递/身份未实现，不是宣称已证实消费者故障；生产仍b646不变。修后同一完整run033 **115PASS/0FAIL/0GAP/0未执行**，全量 **853PASS/5既有skip**（63.20秒），115技能/compileall/diff PASS，Astra实际diff无必要修订。257旧正式现场/100fixture保持，软件实际模型及Supply下游0，source `aff2ed40dd85dbec74f9a8a894b1688626116e6b2de5b145d8e0443597f7ea53`。

软件证明任务说明/身份/合同传递，不证明模型语义改善，更不承诺根治。本次新真实证据须在另一固定版本及全新32项batch09中取得；旧batch08与全部历史FAIL保留、不倒算、不放行Smoke。按既有授权窄提交、安全加载/套餐/实时空闲检查后继续原16主题和原门槛。

## R4 batch09 固定版本与安全加载（2026-10-07，真实结果未定）

§13.21/13.22固定commit89bc154d228f443e784632cd74386c54d2558ab9/sourceaff2ed40dd85dbec74f9a8a894b1688626116e6b2de5b145d8e0443597f7ea53，仅14获批源码/测试/fixture/Task文件，凭证/运行产物0，无push，用户其余工作树保留。run033115矩阵PASS/853全量PASS/5既有skip、115技能/compileall/diff及AstraCONTINUE。

实时8旧Owner有效操作0，各批unknown/pending/submitting/release待办0，Gatewayactive/lost/audit0；同Key文字套餐90%/98%，无fallback，实际账单UNKNOWN。257旧正式现场/100fixture及全部八旧批原件SHA保持。实际raw-stream停服后精确备份130,268字节、SHA537989e82995f296b765a2674e19cae31e2f822275a00b37de39310e6706217f核验，13:41:53 Web/Gateway新PID4791/4789安全加载，HTTP200/Gateway空闲。无进程内SHA端点，证据为新PID/时间/执行文件/cwd与固定源。

原16主题和独立oracle不变，冻结32全新独立正常确认Creation，真实成绩尚未产生；逐项实际Prep/A/B/Truth与独立语义评分，正式双PASS才继续。实际Supply/Provider/生成/TTS/Build禁止，全部历史FAIL保留，Smoke=NO。[加载记录](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-release-loaded.json)。

## R4 batch09 batch09：正式合同PASS，屏幕/手部无来源硬化语义FAIL（2026-10-07，STOP）

固定89bc154d/sourceaff2的新32项首项《桌上的两张纸》，正常Prep/A/B0/Truth初次及一次Truth报告修复五原run全部ok/released。A/B正式合同无Planning repair；Truth初次误将创作短句作为supported_paraphrase，沿原有一次报告修复改为creative_expression/sources[]，正式Truth/Persist/Load及原生Supply前切点通过。

独立Main及Astra STOP：正式required“**不出现任何屏幕**”无冻结硬来源。确认稿和Preparation仅静态桌面两张白纸/15秒/9:16/silent/后期正文，Mode Visual Bible还列screens为日常素材；同Need明确soft preferred_visual_details包含no screens，不能以A自行写入description的禁令自证新增授权。禁止可识别手部也未查到冻结hard来源；禁止编造私人事实/画外人物不是禁止所有画内对象。纸空白有依据不计失败；全部实物印字/品牌包装/招牌存在部分Mode文字边界，不打包定罪，本次无需依赖范围争议即可FAIL。

本次15秒保持画面及整个function使用/叠字/作者来源义务正确postproduction；两张白纸/image/9:16/silent/SCRIPT和Mode风格/留白preference保持，说明改善而非整体语义通过。原required语义1/1保留，无遗漏/降级，但无来源hard至少2项使独立语义FAIL；正式合同/TruthPASSED不能抵消。评分不改正式产物、不降级救场。

本批1项语义FAIL/31未执行、held-out0/16。A/B初始无需Planning repair1/1；含Truth首次无报告修复0/1；最终正式合同1/1执行项（计划1/32），独立语义0/1。Planning repair0/N/A，Truth report repair1/1，NORMALIZE0。281.806秒、Planning含Truth219.945秒；5实际提交/30assistant/29工具/23原请求pending观察，9应用callback含4缓存原请求重入，重复实际提交0。两Truth请求共享同session、request hash与run独立，审计按一个实际transcript window计数一次，不把两run的同一会话重复累计。套餐90→89%/周98→98%，实际账单UNKNOWN。

Supply/Provider/生成/TTS/Build/状态越界/工程介入0。固定源/工具/原16主题/SCRIPT、257旧正式现场/100fixture及全部八旧批原件保持；五原run已释放，各批pending/submitting/release0，Gatewayactive/lost/audit0。正式原件SHA评分前后不变，raw精确归档/脱敏会话/完整请求/独立评分保存batch09受保护根。后31项不启动、历史FAIL不恢复不倒算，Smoke=NO。[完整指标](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-actual-run-summary.json)、[独立语义FAIL](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-independent-failed-review.json)、[Astra](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-astra-review.txt)。

后续不只增加相同语义提示。本例暴露A生成的描述被当成自身硬来源，而B的target/strength说明未能阻止无来源属性进入required。下一步先调查正式硬条款能否只由程序投影冻结Creator/Director原句、将模型创意描述/检索意图与硬来源分开；保留独立语义审核，不假装引用存在就证明含义正确。涉及新输入协议/责任边界须先单一Task设计及Astra前置复核，未完成离线证明前不另起真实批。

## 硬来源治理修前及组件进度（2026-10-07，软件未完成）

Task§13.24–13.25.1经Astra两次MODIFY闭合后CONTINUE，仅认可软件实施。batch09的14实际原件逐字SHA及3份元证据进入脱敏fixture，历史100文件保持，合计117。run034/035新第47行为1PASS/2FAIL；完整修前run036为116PASS/2新增保护FAIL，生产aff2和257旧正式现场保持，不能用旧软件853PASS掩盖新缺口。

应用层来源组件新增后，run037为5PASS/2FAIL，run038为6PASS/2FAIL：已执行旧@6真实原件精确正式PASS/独立FAIL回放、目录资格及错scope保护、真实默认vs显式同值、硬filter不能用soft/post放行、合法创意和错误realization独立语义边界、真实Handoff读取及伪上下文/Mode/缺正文/原件篡改拒绝。两FAIL是B依据Schema与scalar control尚未接入产品链；没有skip/xfail、没有把已接受来源ID当语义PASS。run038工作树sourceb878为未提交组件指纹，117fixture/257现场前后保持；py_compile/diff通过，不替代全量软件出口。

下一步接入同一@7 A/B/repair/身份/checkpoint/persist/load与新旧版本回归。未commit/push/restart，服务仍旧固定89bc，新真实模型/素材调用0，batch09及所有历史FAIL保留，READY_FOR_MATERIAL_SMOKE=NO。[前置复核](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-authority-design-review.txt)。

## @7 正式链集成中间证据（2026-10-07，最终软件验收进行中）

Task§13.27完成实际来源/A/B/repair/身份/checkpoint/persist-load接入。run039测试文件缩进错误导致未收集，原记录保留；修正后run040为131PASS，run041为135PASS/0FAIL/0GAP/0未执行，257旧正式现场/117fixture保持。真实内部Owner→Preparation→A/B→Truth→正式persist/load→Supply前切点及隔离Supply/Observation使用产品@7；旧风险fixture明确@6，不冒称旧固定回复已经具备新依据。

首次全项目873PASS/5既有skip、115技能/compileall/diff通过，随后Astra冻结前MODIFY提出空control Schema、@7诊断字段和完整B消息容量三处一致性缺口。已最小修订并补跨批初B/repair Schema实际校验，以及JSON能容纳而完整B消息超限时所有B零提交的原生验证；最终矩阵和全项目检查重新执行，本段中间结果不得用于最终SHA冻结。

未commit/push/restart，新真实调用0；服务仍89bc，batch09及所有历史FAIL保留，READY_FOR_MATERIAL_SMOKE=NO。

## @7 硬来源及control最终软件验收（2026-10-07，SOFTWARE_ACCEPTED）

最终run042为135PASS/0FAIL/0CONTRACT_GAP/0未执行，全项目873PASS/5既有skip，115技能/compileall/diff通过，未改前端。生产203文件SHA`bf527ce1b565409817a5c21e0dc8029e6ca3ad73681bd619493fc4bd17be9caf`、257旧正式现场和117fixture保持。Astra冻结前MODIFY三项已修正并实跑后最终CONTINUE。

这是来源资格、完整control审查、原生集成和恢复的软件出口；不是自然语言语义正确性或32项真实Eval成功。合法来源ID下错误realization仍独立FAIL，純声音语义仍须真实验收。完整[JUnit](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-authority-software/junit.xml)、[stdout](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-authority-software/pytest.txt)、[摘要/source清单](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-authority-software/software-summary.json)、[Astra](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-authority-software/astra-review.txt)保留。

当前尚未提交/加载/新真实运行。旧batch09及历史FAIL不改写，READY_FOR_MATERIAL_SMOKE=NO；下一步窄提交、安全加载和全新32项R4，禁止实际Supply及下游。

## R4 batch10：@7固定版本已加载，真实评测进行中（2026-10-07）

固定commit`3be0ff946c29c8871a8f34de015c8b3944316ac7` / production203文件SHA`bf527ce1b565409817a5c21e0dc8029e6ca3ad73681bd619493fc4bd17be9caf`，23个选定源码/测试/fixture/Task文件凭证检查0命中，未push，其他工作树保留。run042135PASS/873全量PASS/5既有skip、115技能/compileall/diff、AstraCONTINUE。15:00:18 Web10168/Gateway10166安全加载，HTTP200/Gateway空闲；实际raw-stream停服后精确备份1,178,673字节、SHAbf6d88c5c98eeffb58971c3bc2ceb0dbf379d105c1dd847f3eab2d6d8dd0f0bf。无进程内SHA端点，版本证据为新PID/时间/执行文件/cwd与固定源核对。

实时8旧Owner有效操作0、各批unknown/pending/submitting/release待办0、Gatewayactive/lost/audit0，257旧正式现场/117fixture和九旧批原件保持。仅已购文字套餐额度89%/周98%，禁止余额/现金/超额/回退，实际账单UNKNOWN。原16主题与独立oracle不变，32新正常Creation隔离冻结，第0项开始真实Prep/A/B/Truth，尚无评分。正式合同与独立语义双PASS才下一项；实际Supply/Provider/生成/TTS/Build禁止，历史FAIL不恢复不倒算，Smoke=NO。[加载记录](fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch10-release-loaded.json)。
