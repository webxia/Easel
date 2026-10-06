# 独立真实 Material E2E（2026-10-06）

状态：FAIL / Planning 自动失败停止 / 未进入 Material Supply。新作品 `cr_94b5d27f5fb140de85981cecba009a9d`；只验收到 MATERIAL_READY，不进入 Authoring、Build、视频 Quality。

## 固定基线与加载

- 分支 easel-studio，HEAD `5919a9dedd17b1c91b45d0854f55757933461463`，生产源码集合 SHA `d1ed4ec4c2944b4f488cbeecc07208696ece0a176405393fe5c97f1a296ba016`。既有文档改动保留，生产源码无未提交改动。
- 本次新 Creation 创建前，在所有旧委托无活动操作、Agent终态/已释放、执行锁可用、网关 active=0/queued=0 后，通过既有 launchd 服务重载 Web 与 Easel 网关；不改代码/配置，不重启 Hypit。
- Web PID 34647、网关 PID 34659；加载核对时间 2026-10-06T00:56:25.466763+00:00。OpenClaw 已安装收尾修复模块 SHA 654bb2d9753e0a354320a70bdb96a120e9d5c0780e3d76f0e69bf08f4e2dd6d6，在新网关进程启动前已落盘。
- 按 AGENTS.md 真实 E2E 前 Astra 只读复核：CONTINUE。复核未修改文件或调用 Provider。
- 当前声音/BGM策略沿用现有配置，不改阈值或结论；bgm-practical@4 广泛能力留出 FAILED 的历史仍保留。本次只记录该当前版本一次真实新作品结果。

## 正常创作入口

- 本线程用户独立授权新作品最多 ¥10，仅 MiniMax 图片与现有预置旁白，不含视频生成、AI音乐或 Build；旧预算不转授。
- 2026-10-06T00:56:58+00:00 从正常 Web 新对话提交与旧测试相同的纸笔清单主题、原全文旁白、约45秒/9:16、独立文字、真实旁白及合法器乐BGM要求。未复制旧Plan、Need、素材或报告。
- 正常确认前对话纠正模型擅加可读中文/同清单约束及环境音替代BGM；仍保持完整视觉表达、旁白、BGM及七段分镜，不替模型手造MaterialPlan。
- 2026-10-06T00:57:29+00:00 通过正式 `/delivery/material-endpoint` 设置终点并回读：未确认、无Attempt，终点 MATERIAL_READY。第一次缺少正常Operator会话的请求返回401、无变更；建立正式同源本机会话后调用成功，未绕过认证或暴露凭证。

## 运行记录与验收口径

完整本机脱敏记录目录：`/Users/xgx/Library/Application Support/Easel/acceptance/material-independent-2026-10-06`。包含 preflight、连续 timeline、Creation、完整正式规划及Material相关JSON/文本快照、素材字节SHA目录和最终对账。实际Creation/Attempt、原媒体及系统原报告仍留在正式存储，不手改、不删除；认证、secret、原始凭证日志不归档。

运行后若出现代码修改、人工生成/补写素材证据、审核放行或工程救场，本次立即 AUTONOMOUS=NO；不倒算恢复结果。确认前正常方案讨论、范围明确的预算确认与预运行服务加载独立列账。

PASS 需当前完整required coverage=100%，视觉/旁白/BGM全部正式准入，Rights/Match/Readiness及正式MATERIAL_READY终点成立，AUTONOMOUS=YES。瞬时Gate不替代Delivery终点；费用占額不冒充实际账单；网关派发/Provider适配调用不冒充完整HTTP或模型内部计数。


## 正式确认与自主运行

- 2026-10-06T00:59:38+00:00 第3版完整方案经正常作品画布确认；方案SHA 29ef323811f756f2ba33fda33bba4aa78ce8b7bd5c7e00830f00ddbcf89085ae，视频方案SHA ec82a3757c890af691990fe910c56dd8dd7308747d18d3c1892b1d3b0edc9821。三轮正常方案对话，没有改正式Plan/Need/冻结文件。
- 当前委托独立预算¥10，音色 male-qn-qingse、image-01、speech-2.8-hd；当前Brief明确不含视频及AI音乐。输入使用声明、当前Creation/方案、终点在同一次正式确认中登记。
- 原Owner自主开始Preparation，Prepare initial=1，已知run easel-c726ea69f3204b40889f07b9e8a6ab18；无人工Retry。

- Preparation正式HANDOFF_READY，Attempt `fa_2368857a95b3c017098064d189ce84e4`，工作区 `/Users/xgx/.easel/hypit/workspaces/cr_94b5d27f5fb140de85981cecba009a9d/fa_2368857a95b3c017098064d189ce84e4`；原Owner自主进入Planning。当前无采购、Authoring/Build未提交，生产源码SHA仍固定。


## 终态、根因与最终对账

- 自动停点：2026-10-06T01:09:53+00:00（北京时间09:09:53）；原Owner `status=failed`、`operation=null`、`exhausted_operation=fa_2368857a95b3c017098064d189ce84e4:prepare`，同操作3次失败。失败为 `Planning 要求合同无效：Planning 要求文件须覆盖全部视觉 Need`。没有人工Retry、模型补写、代码修改、报告篡改、人工审核或预算变更。
- 真实初次Planning草稿曾不满足schema，系统自身派发两项结构修复；最终MATERIAL_PLAN可通过schema，但MATERIAL_REQUIREMENTS根结构仍无效。源码 `easel/materials/application/visual_contract.py:249` 要求根对象的键恰好为全部视觉Need ID；实际根键为 attempt_id/context_refs/creation_id/plan_id/visual_requirements，是包装对象。嵌套visual_requirements数组已有7视觉Need，另混入4音频Need；不能凭嵌套内容完整认领符合契约。不是素材检索/音频审核失败，也不是需要手工补一个视觉条目。
- 当前草稿由Planning实际产生11 Need：8required（6视觉+1旁白+1BGM），3optional（收尾视觉+2音效）。未手造或修改其importance，未删减/放宽Need；正式Planning、Truth和MaterialPlan尚未建立，正式覆盖报告不存在。草稿对应准入0/8仅是未进入供给的参考，不作为正式Readiness覆盖。
- Material目录未创建，Supply/搜索/获取/生成/观察/Rights/Match/Readiness均未执行；无MATERIAL_READY、Material endpoint result、Production Authoring、Build、输出或Quality。工作区中系统初始化的AUTHORING_TASK.md/productions/runs目录不是派发Authoring的证据；实际authoring=READY_FOR_EXTERNAL_AUTHORING、execution=NOT_SUBMITTED、outputs={}。
- 准备冻结4文件SHA逐项吻合最初Preparation snapshot hashes，3份handoff副本逐字一致，Production Brief内联对象与冻结快照相同；所有生产源码逐文件SHA与预登记一致。旧四项已登记Creation记录SHA均未变。服务仍为原新加载PID34647/34659，本次确认后未重载。
- 四个Delivery run均终态及runtime released，网关active=0/queued=0，执行锁可用；耗尽边界阻止原Owner新派发。保留完整原Creation/Attempt、两份规划JSON、冻结输入与失败历史，不继续修复或另建第二次验收。

### 时间、调用和费用

- 正常入口创建08:56:58→自动停止09:09:53：12分55秒（775秒）。正式确认08:59:38→自动停止：10分15秒（615秒），含所有系统观察与结构修复。没有进入素材阶段，不给素材齐备耗时。
- 正常方案Agent请求3次；Delivery Agent真实派发4次（Preparation1、Planning1、结构修复2）；Prepare计量4/24。观察操作/轮询不当模型调用；原Delivery会话保存47条assistant消息，网关内部模型HTTP/自动续段次数UNKNOWN，不把7项外层派发当作精确内部API总数。素材Provider适配0、生成核价/提交0。
- 用户独立授权素材预算¥10，实际生成提交0、占额¥0；未发生任何本次生成采购，额度未转授。模型/总实际账单UNKNOWN。网关usage cost的零值是当前记录占位，不是免费模型或实际费用零的证据。
- AUTONOMOUS=YES仅表示正式确认后全程由系统执行、无人工工程救场；本次E2E=FAIL，未自主达到MATERIAL_READY。代码和工程干预0；运行前固定版本/安全加载与确认前正常讨论另列，不倒算历史工程恢复成功。

### 最终八项

MATERIAL_E2E = FAIL
AUTONOMOUS = YES（全程无工程救场；未达终点）
REQUIRED_COVERAGE = 未建立正式覆盖（Planning草稿0/8）
ELAPSED_TIME = 12分55秒（正式确认后10分15秒）
CALLS = 方案3；Delivery Agent4；素材Provider0；生成0；内部模型API次数未知
COST = 生成占额¥0/¥10；模型及总实际账单未知
ENGINEERING_INTERVENTION = 0
BLOCKERS = Planning要求合同根结构无效，原Owner自动三次失败停止；未进入素材阶段。

完整脱敏原始记录、连续时间线、冻结快照、Gateway会话和终态对账保留于上述本机目录；最终机器对账为final-result.json。失败现场原件仍在正式Creation/Attempt存储。


## 后续 Planning → Material 合同软件修复（2026-10-06）

此节记录用户另行授权的确定性软件修复，**不改变上方原运行 FAIL，不恢复原作品或启动新 E2E**。只修改 `visual_contract.py`、`web/app.py` 的合同交接与相关测试；未重载 Web/网关，未调用 Provider、生成、Authoring 或 Build。既有文档修改保留。

### Canonical 与根因

唯一 canonical **Planning sidecar** 仍为根对象 `visual_need_id → {clauses, queries}`：必须恰好包含 Plan 的全部 image/video Need（required/optional 都保留），不能含 audio ID 或身份包装。clauses 使用 `path/text/kind/preference_path`，逐段引用冻结 Need 原文；kind 为 required/preference/postproduction/unresolved，非偏好引用为 null。查询是供应元数据，不是视觉条款。Material consumer 使用经同一 `validate_compilation()` 绑定后的 input/response/contract，不直接消费模型包装。声音 Need 留在 MaterialPlan，走原 Voice/BGM/SFX 合同。

直接偏差属于 **Planning producer**：初始提示只有简略形状，没有正式要求 schema，repair 未携带该合同；真实文件生成包装数组并混入声音。逐层回放还发现路径别名、空引用、软偏好漏项，以及 V03/V04/V05 将 U+2018/U+2019 单引号复制为 ASCII 单引号。现有原文覆盖/importance 规则不应放宽。

程序侧还有两项衔接错误：`sources_for()` 把具名标量查询变体误当视觉原文；Planning 写入 `requirements-digest(input)`，观察端读取 `requirements-digest({compiler_policy,input})`，无法复用同轮合同。它们属于元数据与缓存交接错误，不需要模型推断或重写创作意图。

### 最小修复与边界

- 正式 schema 由 `PlanningRequirements` 定义，初始提示、repair 提示和输入 validator 共用；canonical 输出结构不变。
- 入口只转换本次已证实 wrapper，严格核对 Plan/Creation/Attempt/context_refs、行字段、未知/重复/缺失 ID；只有当前 Plan 的 audio ID 可排除，Plan 本体不变。原 JSON 文件不回写。
- 仅识别 `modality_spec/visual_style → modality/visual_style` 与空引用 → null；仅对同位置、等长且 frozen source 为弯单引号 / copied text 为直单引号的差异绑定原始 source。无反向替换、其他标点或通用 Unicode normalization；canonical map 仍严格逐字匹配。
- 只有整条缺失的显式软偏好可从原 Plan 原样补入 preference；必要条款缺失、部分覆盖、改词、未知路径、偏好升级均拒绝。原 kind 不重新推断，含 intent/function 的既有分类保持。
- 精确排除三个已证实查询 metadata 字段，不宽泛忽略未知文本约束；producer/consumer 共用缓存键。旧键仅在新键不存在时读取，仍重新核对 frozen input/response/contract；坏新缓存不能回退或重分类绕过。
- 不新增模型重试，原有有界修复策略保持；此真实结构的合同处理成功路径无需 Planning、repair 或分类调用。

### 确定性证据

原两份 JSON 字节保存在 `tests/fixtures/planning-material-contract-2026-10-06/`，来源及 SHA 见其中 README。回归验证完整 7 visual、8 required / 3 optional、4 audio 不变；全部必要源文字及软偏好保留，正确原文弯引号进入绑定 contract。负例覆盖缺失 optional 视觉 ID、重复/未知 ID、错身份/冻结 refs、必要原文遗漏、同长度实词改变、删除引号、未知路径、软偏好升级/部分覆盖、canonical 引号漂移和 JSON 重复键。

集成回放通过真实 Planning executor 校验并写入派生合同，再以原持久风格默认规则进入视觉 consumer。正常键和旧键均命中全部 7 visual，分类调用被测试协议断言禁止；坏新键即使有好旧键也拒绝。Planning/repair 调用被 pytest.fail 禁止，所有原规划文件字节保持，audio Need 原样。观察只用本地 fixture 图片和假响应并返回 uncertain，不能冒充 MATERIAL_READY。

验证：Material control / Creation Preparation / Material integration / Need compiler / Matching / Advanced Matching 共 **248 passed，14.56秒**，两项既有依赖弃用提示；等长负例精化后 12 项回归再通过。115 技能合同、compileall、diff check 通过。Astra 前置及最终只读复核均 CONTINUE。无前端改动，未重复 lint/build；未跑全量测试或真实 E2E。

原工作区 MATERIAL_PLAN SHA `13085a5d247f4a7f128abdfdf813201016d070e96e08c5b43fa370067a3b1516`、MATERIAL_REQUIREMENTS SHA `c40e165d0c30d9177dcaa8fe08552e4d2b74b91dfde9b4a8ebe2c81e4c402f59` 与 fixture 字节相同。原 Delivery 仍 failed/operation=null，updated_at=2026-10-06T01:09:53+00:00。

ROOT_CAUSE = Planning 输出偏离 canonical，查询元数据误入视觉原文，producer/consumer 缓存键不一致。
CANONICAL_CONTRACT = 全部视觉 Need ID → {clauses, queries}，声音留在 MaterialPlan 的声音合同。
FIX = 同源 schema、严格具名入口转换、原文绑定和统一缓存身份。
REGRESSION = 真实原始结构确定性通过；248 项相关测试及合同/编译检查通过，无额外分类调用。
CONTRACT_CHANGED = NO（Material V1.3 语义及 canonical 输出合同不变；新增严格具名输入适配）。
READY_FOR_NEW_MATERIAL_E2E = YES（仅本次软件前置；新运行须另行启动并核对加载版本/预算）。
