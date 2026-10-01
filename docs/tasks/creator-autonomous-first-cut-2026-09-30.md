# Easel V1 自主首版与 Director 全链执行：唯一实施方案

状态：用户已批准按本方案实施（2026-09-30）。本文件替换此前流程重审和自动化候选草案，是本轮唯一实施 Task；旧方案通过 Git 查询，不再作为并列实施依据。当前完成情况与测试证据只汇总到 [Current State](../02_CURRENT_STATE.md)。

## 1. 两个不可拆开的产品目标

1. Creator 确认委托后，Easel 持续自主交付基本可看的首版；正常制作不依赖 Creator 或工程人员推进。
2. 同一个 Creator + 同一个 Director / Creative Mode + 不同 Content，Director 判断贯穿 Planning、Material、Voice、Production 和 Quality，产出风格可辨识且一致的作品。

风格一致是原始 V1 核心目标，不是后续补强。主题、观点、故事与具体镜头随内容变化；不以固定场景数、故事模板或同一 BGM 代替导演一致性。单片成功、Stage 全通过、Mode 哈希一致均不足以完成目标。

## 2. 已核实根因与改造依据

- 推进分散在页面副作用和进程内 Authoring 任务，缺少对首版持续履约的后端责任；人工素材核对、逐次确认和阶段重试弥补系统能力缺口。
- Mode 文件与哈希确实冻结并传入 Planning；Planning 完成检查主要验证身份、Schema 与非空文件，没有验证导演要求已在执行中落实。
- ProductMaterialSupply 未向已有 Compiler/Library 接入 creative_mode_terms/director_preferences；本次七个 Need 无 preferred_style，七条 Match 的 director/continuity 分数均为空。默认视觉分析器未启用，匹配依赖人工观察。
- VoiceNeed 的 delivery_description 未进入 TTS 请求；现有请求只传文本，使用运行配置音色及固定 speed/vol/pitch。
- 隔离 Production Authoring 主要读取文字与素材 JSON，媒体字节在 Agent 结束后才交静态校验。本次文稿要求 ducking，实际只有固定 BGM gain；字幕沿用 Planning 时间格，未形成真实逐句语音对齐依据。
- Hypit 执行原生工程，不替 Easel 推断导演意图。自动 QC 主要为文件/音视频流/解码检查；style pass 来源于 Creator 接受，未形成自动导演审片。
- 36 秒作品的实际问题、修复与用户接受见 [音画验收](../acceptance/creator-audio-quality-e2e-2026-09-30.md)。三个 Attempt 是同一内容修订且未绑定 Profile，不证明跨 Content 的 Creator 一致性。

代码入口：web/app.py（确认、Planning、Authoring）、easel/creation_preparation.py、easel/integrations/material_supply.py、easel/materials/application/{compiler,matching,intelligence,generation_modalities}.py、easel/integrations/openclaw_authoring.py、easel/integrations/hypit/{handoff,workspace,service}.py。

## 3. 最小责任边界与完成条件

| 现有归属 | 必须承担的责任 | 完成条件 |
|---|---|---|
| Easel / Creation Workflow | 唯一 Delivery Owner，持有委托、推进、处理缺口与失败 | 当前输出通过首版质量检查并可审阅，或有证据说明无法履约；用户接受独立于中间制作完成 |
| 现有 Planning + Production Authoring | 连续的 Director 判断，把内容与 Mode 转成选材、声音、节奏、字幕和剪辑决定 | 决定落实到实际原生工程；只有文稿不算完成 |
| Truth | 保护真实事实、身份与表达边界，区分事实、观点、假设 | 影响交付的真实主张有依据或得到合适处理；普通改写不默认逐句人审 |
| Material / Voice | 提供实际观察过、权利条件成立、适合表达的素材与语音 | 必需素材可用于具体剪辑，声音身份、实际时长和必要时序明确 |
| Hypit Production | 执行明确的音画、时间线与合成安排 | 候选视频身份正确且可播放；不补猜导演意图 |
| 现有 QC / Review | 系统先检查可看性与明显 Mode 偏离；Creator 最终取舍 | 检查绑定实际输出，关键缺陷解决；人审接受单独留证 |
| Recovery | Delivery Owner 调用的内部恢复能力 | 从可信结果继续，不重做成功工作，不重复不确定提交 |

不新增 Director 模块、第二套 Workflow、第二套 Production Domain；责任名称不对应新服务或新阶段。复用当前状态和持久记录，页面展示只读投影。

## 4. 委托、授权与恢复

- 确认冻结意图、事实边界、Mode、规格和费用权限；内部选材、镜头和剪辑草案可在范围内版本化调整。实质改变委托才再次确认。
- 本作品文字使用声明随同一次方案确认单独留证，绑定声明版本/范围、作品与方案；不把费用批准、普通聊天或旧确认当作该声明。它只记录 Creator 的输入授权来源，不替代 Provider 输出许可、第三方权利或发布条件。
- 新声明明确包含按委托以文字生成图片/视频、改写、预置旁白与剪辑；旧声明只保留原范围，不因升级自动扩权。生成素材的内部使用由当前输入授权、请求时已审核协议版本、模型/请求/实际资产身份及素材观察共同认领，不能由“生成成功”或费用批准直接推导。沿用正式 Rights/Match/Readiness；缺证或已有不利权利条件不覆盖，入库和公开发布仍分开。
- 正常选材、补料、技术重试、格式修复与基础质量检查由系统执行。只有必要且系统无法处理的事实/权利问题、实质意图变化、授权外费用等才升级 Creator。
- 持续推进、执行身份、检查点、重试与费用记录附着现有 Creation/Attempt，复用现有原子写入/锁/幂等/对账；刷新、关页、服务重启后恢复。
- 成功步骤复用有效证据；提交不确定先对账。恢复不能自动重复购买、复制过期批准或无限重试。
- 确认前说明允许操作、费用依据和执行边界。已有授权内不重复询问，零第三方费用不虚构正预算。本地预算不是 Provider 硬上限；无法判断是否在授权内时停止提交。
- 逐次付费批准、零费用确认和显式补料策略涉及的现有 ADR/Task 条款随对应实现一并修订，记录授权来源；不绕过正式 Rights、Match、Readiness、身份或费用语义。
- 旧 Creation 不迁移、不自动入队、不因启动新代码恢复运行。自主委托只作用于明确带有新委托记录的作品；本轮测试全部使用隔离 Fixture。

## 5. 必须修改与复用

| 改造项 | 最小改动 | 复用 |
|---|---|---|
| 持续交付 | 页面推进迁后端，持久化执行、检查点和恢复 | Preparation、MaterialProductOrchestrator、Authoring/Hypit API、现有存储 |
| Director 执行要求 | 当前 Mode 中 V1 支持的少量要求落到 Need、运行参数、原生编排与检查，保留来源和适用范围 | Creator Context、Mode、Treatment、MaterialNeed、组件/recipe |
| Material | 接通已有模式检索词、导演偏好和适用风格匹配；实际观察主体、区间、光线、运动、限制；有界替换/补料 | Compiler、Matching、Intelligence/enrichment、Library、supply_subset、Rights/Readiness |
| Voice | 可支持朗读要求进入实际请求；绑定已批准音色和参数；真实音频检查与逐句时序 | VoiceNeedSpec、TTS adapter、生成记录、音频素材/hash |
| Production | 给 Authoring 受控素材观察/必要预览/可用区间/语音时序；代码处理身份、路径、时钟等确定性内容，模型负责创作安排 | 隔离 Authoring、Run 转换器、vocabulary、SVML/SVS、局部修改保护 |
| Quality / Recovery | 实际输出检查，定位缺陷，在委托/费用边界内局部修复，只重查受影响部分 | 技术 QC、Review、输出绑定、反馈、恢复/修订 |

先覆盖现有 clear_memo_video，不建立通用风格 DSL 或多 Director 平台。声音、选材和剪辑参数可随内容变化，风格规则的适用范围不能被硬编码成固定视频。

## 6. 删除、合并、内部化

| 当前机制 | 处置 |
|---|---|
| 页面 useEffect 推进制作 | 删除推进职责，页面只读状态/提交必要决定 |
| 正常路径逐 Need 人工匹配、重复试听声明、额外继续按钮 | 系统检查与后端推进替代；人工入口仅真实例外 |
| 非逐字脚本默认全面人审 | 按真实事实风险处理，不以普通改写触发审批 |
| 逐次生成/零费用 Build 重复确认 | 合并到明确委托；保留逐次执行与费用核验记录 |
| 模型填写已知身份/技术字段、猜语法 | 移入现有代码适配和组件辅助 |
| 同一可信输入重复昂贵检查 | 按输入身份及检查版本复用，变化后失效 |
| Stage / Attempt / Runtime / SHA 操作入口 | 必要语义内部保留，退出正常 Creator 路径 |
| style pass 混同机器检查和用户接受 | 分清证据，不用人审证明系统已执行 Mode |
| 风格一致性作为后续补强 | 取消，纳入本轮 V1 完成条件 |

## 7. 依赖、实施顺序与局部验证

依赖：① → ② → ③ → ④ → ⑤ → ⑥。每项遵循 root cause → minimal fix → targeted verification。优先扩展既有高价值测试，不要求新增测试文件或数量。

| 步骤 | 实施 | Replay / Contract / Fixture 验证 |
|---|---|---|
| ① 委托与持续交付 | 后端唯一推进者、授权、派发、恢复、停止条件；内部调整与实质变更分开 | 假执行器验证关页、重启、重复/并发事件、提交超时；不丢任务、不重提、不越授权，不动旧作品 |
| ② Director 决策传递 | 在现有 Planning/Need/Authoring 落实执行要求；修正 Truth 默认阻断；固定有效 Creator/Mode 上下文 | 同 Mode 不同 Content 保留开放叙事；风格要求进入真实执行输入，内部调整不重复确认，越界停止 |
| ③ Material / Voice | 风格偏好、观察、排除/替换/补料、朗读参数、音频时序 | 标题相符但画面不符、主体晚出现、风格不符、权利缺失、旁白过长；验证实际请求与时序合同，已有音频不再生成 |
| ④ Production | 根据素材区间与音频时序原生编排，确定性技术辅助、字幕与混音 | 已存 Planning/Bundle 局部回放及本机静态合同；时序、取片、配乐变化、局部修改不漂移声音/文字；不提交真实 Build |
| ⑤ Quality / 修复 | 实际输出检查、缺陷定位、有界局部修复 | 既有/确定性短媒体：近黑主体、低对比字幕、旁白截断、BGM 过强、内容错配；检出关键问题、只修相关部分、不无限循环 |
| ⑥ 跨内容回放 | 同 Creator/Mode 的 3～5 个不同主题串接局部能力 | 固定执行结果和观察证据验证风格贯穿且内容/叙事不同；恢复不改风格、不重复 Provider |

① 完成不等于产品完成，不能只自动串联旧链路。⑤ 和⑥完成后才评估真人验收准备度。

## 8. 首版质量边界

- 内容符合委托，没有未经支持的身份或事实表达。
- 实际使用区间呈现所需主体，裁切和字幕不破坏可读性。
- 旁白完整，字幕有实际语音时序依据，BGM 不明显压住旁白。
- 关键音画与剪辑符合当前 Mode，避免明显重复、空转或风格偏离。
- 确定性指标用确定性检查；内容/素材关联和必要风格判断用实际媒体观察。软偏好允许记录偏差，不把所有审美变成强制门禁。
- 分析能力缺失不以人工已确认填补，不伪造自动 PASS；Fixture 通过不能宣称真实感知效果已验证。
- 首版可审阅与用户接受/Selected Output 分开；最终确认仍绑定当前输出并保存内容库，不自动发布。
- 接受和入库不等于取得发布许可。实际选用素材的使用范围随导出、审片和内容库保存；仅限内部制作的成片仍可被接受与保存，发布时继续遵守原有使用范围和最终审片要求。

## 9. 执行边界与交付

本 Goal 已获实现授权。保持 Creation/Preparation/Planning/Material/Hypit/Review/Selected Output 主链，不改变 Material Layer V1.3 的素材/权利/匹配/准入语义，不大规模重构，不顺带扩展修改类型。

本轮不修改或继续当前 Creation，不调用付费 AI，不启动真实 Build 或完整 E2E，不重载服务去推进现有作品。Provider 改动核对官方契约；Hypit 改动核对本机版本与源码。所有测试确定、隔离、不依赖真实凭证。

必要局部验证通过后完成相关 lint/build/compile 检查；检查 Secret、runtime、产物排除后按用户已授权要求提交并推送 origin/easel-studio。不得推 upstream、force push 或改写共享历史。

完成报告区分已实现、局部证据与真实验证缺口，使用 FIXED / PARTIAL / REMAINING / TESTS / READY_FOR_HUMAN_E2E。真实 E2E 由用户随后启动；不得把局部回放等同真人成片验收。
