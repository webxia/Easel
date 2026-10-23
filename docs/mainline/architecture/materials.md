# Easel 素材层架构

状态：**素材层职责与设计合同**。具体版本的软件/真实服务验收只以活动Task和运行记录为准。原G1设计及后续增补的来源状态为 IMPLEMENTED_SOFTWARE / REAL_SERVICE_VALIDATION_PENDING；依据[五类素材审计](../history/v2/17_MATERIAL_LAYER_AUDIT.md)、[正式需求](../product/requirements.md)、[唯一实施合同](contracts.md)，按用户本轮授权进入实施。此文是内部设计，不代表运行验收，也不替代公共Plan/Editor/Operation合同。

## 1. 技术选择与理由

| 议题 | 本轮选择 | 不选及理由 |
|---|---|---|
| 总体 | 同进程模块化：冻结上下文→导演意图→MaterialNeed→库/Provider→用途绑定→Editor准入 | 不加新Agent平台/队列/向量库，不恢复V1运行状态 |
| 创意与程序 | 导演理解创意、产生检索词/类型/音乐和声效意图、看听实际素材后选择；程序管身份/范围/时间/权限/回执 | 不用关键词正则替代语义，不让模型填Key或授权 |
| 上游适配 | PlanDocument schema1不变；新增任务私有有界MaterialIntent，引用scene_id，绑定完整冻结上下文摘要 | 不新建可独立确认的第二方案，不给公共Plan加必填字段 |
| 模型调用 | 需要语义解释时一次有界素材意图解释，多源共用；静音且画面已被必用素材完全覆盖时走零额外调用；稳定namespace，与既有补料决定分离，持久化复用 | 不为每个Provider/候选创建Agent；不重置ordinal串回执 |
| 资产与用途 | 内容寻址、来源/权益逻辑记录、material_uses用途绑定分离 | 不按SHA合并Rights，多场景/声效事件不能互相覆盖 |
| 检索 | 本地资格优先，资格后截断/去重；外部按本片授权白名单；缺配置与真实无结果分开 | 排名不是导演接受，任意音频不是已验证BGM |
| 图/视频源 | Pexels/Pixabay保留，修参数与复用；Unsplash仅主动preview | 其热链/使用条款未有完整生产适配依据，不能只加tracking就自动导入 |
| BGM/SFX | 首期复用受许可本地音频和reviewed_public有限清单，统一Need(audio,role)；明确库存不足 | 不臆造Pixabay音频API；新Freesound账户/授权另有准备，不能谎称已接通 |
| 旁白 | 保留VoiceTasks/Operation/句段，显式增加minimax-speech-v1原生协议 | 不整体搬V1段落Voice，不自动换voice_id或用其他免费声音替代 |
| 编辑/QC | 使用原AudioClip时序/增益；只选中依赖；render前重验，QC独立实际视听 | Material不拥有导演权、成片QC和Creator接受权 |

## 2. 流程与责任

```text
不可变Plan + 六维画像快照 + Director版本 + work_inputs
 → FrozenIntentCompiler（任务内部，不改Plan）
 → 现有MaterialNeed：image/video、music/audio、sfx/audio+事件
 → 本地合法候选 → 已授权外部源 → 下载/检查/入库
 → material_uses + 作品artifact → 原schema_version/asset_ids
 → Director观察真实候选并输出CreativeEdit
 → 绑定/Rights复验 → 选中资产manifest → 原FFmpeg
 → 完整视频QC → 用户明确接受

scene.narration + 固定VoiceIdentity
 → 专用VoiceTasks/Operation → 句段音频/时长/文本摘要
 → 同一个CreativeEdit音轨，不加入BGM/SFX任意替换池
```

### 冻结意图

使用已有PlanningTasks.context，不读研发AGENTS/历史会话。私有MaterialIntent仅含已知scene_id、有限query/媒体偏好、BGM意图、SFX cue及未决项；每个cue有稳定id、scene_id、时段与语义来源。程序验证场景、时间上限、静音冲突，不把素材意图当成可重写方案。未确定的必用要求明确报告，不用硬编码检索词创造事实。

本轮不以严格字符串引用协议取代导演创作：可自主表达的视听细节仍由导演决定；必须项与可选项区分，必用缺口不可静默省略。任务持久意图绑定context fingerprint，已保存意图恢复不另调用；新用途namespace保持旧调用ID兼容。

### 候选、绑定与再准入

asset_ref表示来源/许可记录，不是物理SHA或一次使用。metadata.material_uses列表保存need_id/role/scene_id和SFX cue时段；同字节可多处用，但每次绑定独立。旧candidate_role兼容保留。旁白句段不能变成音乐，参考素材不得混入制作。

edit前、选择完成后、render前核验被引用素材的catalog、作用域、许可、真实字节和必要署名；已选素材失格不可由另一个候选的可用性掩盖。工程仅保留实际场景/音轨/字幕字体依赖，原候选仍保留，credits只对应真实使用。

### 供应与恢复

运行组合根按本计划有效grant中的provider/model/mode筛选外部源；无远程授权仍可本地复用。已知权益不满足时先拒绝下载。相同来源和实质许可、用途兼容的本地文件重新验证后复用；观察日期不应导致重复下载，但不得忽略许可差异。IMAGE/VIDEO/TTS仍唯一OperationService准入，UNKNOWN不重发。

### 旁白协议

新增显式minimax-speech-v1，复用原SpeechConfig、VoiceIdentity、发送intent/receipt锁和声音缓存；只替换HTTP编码/响应解码。非流式t2a_v2返回JSON/hex，严格有界读入并验证状态、hex、真实音频时长。不从服务名称猜协议，不自动配置音色。http-speech-v1保持原二进制合同。

## 3. 实施包

> W0～W5是原S6-15分工，保留覆盖与测试依据，不是当前新待办；实际执行见对应Task与当前状态。

W1：资格过滤/去重、引用用途合并、来源复用与下载前Rights。W2：冻结意图、SFX供料/用途绑定与模态矩阵。W3：选中依赖和edit/render再准入。W4：MiniMax旁白协议与真实能力目录。W5：正负例、实际合成媒体、生产回归及边界SHA回查。

每包必须有反例：旧失格记录遮蔽新资格、不同Rights同SHA、无授权零请求、未知场景/越界cue/静音冲突、缺音源、重复意图恢复、角色串用、已选素材失格、未选素材不进入credits、错误JSON/hex、未知回执不重发。新代码测试不调用用户真实服务。

### 实际落点

| 责任 | 实现位置 | 验证入口 |
|---|---|---|
| 冻结意图与避免重复解释 | `easel/production/material_intent.py`、`model_operations.py` | `test_material_hardening.py` 的上下文、恢复、命名空间、静音必用素材零调用用例 |
| 五类供料与独立用途 | `easel/production/supply_tasks.py`、`easel/materials/application/supply.py` | 必用/参考、来源授权撤销、BGM/SFX分类及多个事件共享素材 |
| 资格、复用与选中依赖 | `easel/production/materials.py`、`material_binding.py`、`creation.py` | 资格后截断、不同权益记录保留、来源复用、选中失格/引用消失阻断、未选素材不入依赖 |
| 固定旁白HTTP与原生协议 | `easel/production/voice.py`、`providers/minimax_speech.py`、`configuration.py` | 二进制HTTP回归、原生JSON/hex真实音频检查、固定音色/缓存/错误后不重发 |
| 组合链路 | `tests/production/test_five_modalities_flow.py` | 实际worker组合图片、视频、BGM、原生协议模拟旁白、SFX并用FFmpeg渲染到reviewable，禁止自动接受 |

实现没有给公共Plan新增场景上限或压缩其Identifier范围；内部投影精确回查原场景集合。模型语义是否正确、声音是否自然仍必须依赖真实样本，不能由上述程序校验替代。

## 4. 历史验收边界（非当前排程）

G0/G1为本轮审计和内部架构决定；G2/G3软件以实际执行结果记账。真实Provider、BGM/SFX实际库存与自然音色不足必须保持未测/阻断，**历史G4/S6-14准入决定不作为当前禁令；当前执行范围以状态页及本次授权为准**。已有Keys不等于生产调用授权，Creator接受单独由用户决定。

原S6-15任务当时限定了公共合同文件不变及内部修改范围，此限定只适用于原任务，不构成后续开发的文件禁改清单。公共合同与职责变更仍须评估影响，不新增无依据的生产状态机。不满足当前公共合同的新增要求必须单独提出影响分析，不隐式扩schema。官方技术依据见[审计§5](../history/v2/17_MATERIAL_LAYER_AUDIT.md)。
## 5. 来源扩展与历史备选
**来源取舍记录（2026-10-17，非当前任务分配）**：用户明确暂缓 Unsplash，只保留主动预览；不创建音频素材管理 UI。BGM/SFX 改为优先实现不要求注册的 Wikimedia Commons 公共音频 API，以下 Unsplash 方案保留为历史备选、不是活动任务。

### Unsplash —— 显式选图与权利就绪，而非直接开启自动下载

在现有 `UnsplashDiscoveryProvider` 和 Web preview-search 基础上，补一条明确的选图交易：`用户选择 photo.id → 服务端重新核对来源/真实 URLs/下载事件地址 → 适用 Rights 与用途审核 → 追踪下载事件 → 受控取得允许使用的媒体 → catalog 入库 → 作品 asset_ids`。仅当官方 API 规则与用户场景下实际权利同时允许本地用于生成 MP4 时，才发布 production-ready。事件追踪应保存与具体选择/作品相关的幂等证据，**不能在回执未知时盲目再次报下载**；未获使用资格仅展示官方热链预览，不偷渡到现有 `ExternalCandidate` 自动供应列表。

推荐先验收显式选图，再审查是否开放 Director 自动挑选。反例覆盖恶意 photo.id/URL、跳转到非允许主机、Rights 变化、选图取消、未收到成功 tracking 回执、原图与预览来源不同、重复提交/恢复、作品版本变化、取消后无外部请求、仅已用素材署名导出。

### BGM —— 先做真实合法音乐目录，再新增动态搜索源

统一使用已有 `MaterialNeed(media_type=audio, role=music)`；Director 提供情绪、节拍、强弱变化和使用场景，优先从本地已核权利音频检索，再从具名 `reviewed_public` 曲目目录搜索。后续采购或获批的音乐 API 可作为新 Provider，不改变 Edit/Work 外部合同。每个曲目必须有来源/署名/许可/曲长/技术条件；“循环播放、变速、商用视频”分别按 Rights 约束校验，不把搜索结果等于合格曲目。

### SFX —— 专用声音事件索引，不建立第二种音频状态机

使用现有 `sound_cues` 的 `cue_id/scene_id/at/duration/required`，统一音频资产、独立事件绑定；同声效跨多个 cue 可复用文件但不得覆盖事件时间及重要性。初期与 BGM 共用审核来源机制，按事件标签/持续时间检索；未来 Freesound 原始文件下载需 OAuth2，并须确认 API 的商业应用许可，故不默认启用。每条生产 SFX 必须具备真实音频、用途适配、 Rights 和绑定依据。

### 保持不变的公共边界与验收

`PlanDocument`、`MaterialNeed`、`OperationService`、`EditProject` 和 `schema_version/asset_ids` 输出不变。外部来源只做合法素材候选与下载；素材层不生成新导演策略、不允许模型替用户授予权限；FFmpeg 与 QC 仍属原主线。测试先使用 MockTransport 与合法本地媒体，再按实际允许范围验证官方 API；任何实际来源不可用都保留明确 gap。**Unsplash 仍仅预览；音乐/音效新增 Wikimedia provider 的软件实现，但该增补记录当时尚未完成真实文件下载和实际听感，不能据此判断当前G4；具体运行查Task/轮次。**

资料：[Unsplash 官方 API 文档](https://unsplash.com/documentation)、[下载事件指南](https://help.unsplash.com/en/articles/2511258-guideline-triggering-a-download)、[API Terms](https://unsplash.com/api-terms)、[Freesound API](https://freesound.org/docs/api/overview.html)、[商业 API 使用说明](https://freesound.org/help/developers/)。
### 音频自动来源具体落点（真实结果见具名运行记录）

- `WikimediaAudioProvider(role=music/sfx)` 通过单一官方 `generator=search` / `prop=imageinfo` 响应，限定最多 40 个结果并校验官方文件身份（pageid + SHA-1）、`audio/*` 或已识别的 `application/ogg`、原件页、`upload.wikimedia.org`、大小上限和源文件自身 LicenseShortName/LicenseUrl。仅 CC0 1.0 与 CC BY 4.0 进入候选；特定版权声明证据随 Rights 入库，CC BY 署名进入 credits。未知、NC、SA、ND 一律阻断，不因公共 URL 宣称权利。
- 供料不新增工作状态机：`EASEL_WIKIMEDIA_AUDIO_ENABLED=1` 后，`SupplyTasks._allowed_providers` 按作品既有 stock/search 授权分发；`MaterialSupply` 过滤不适用的 music/sfx 来源，下载后先调用 source SHA-1 对照，随后走共用受控下载、技术检查、入库、恢复和 Editor 绑定。
- 公共 API 访问无需账号，使用带 Easel 项目公开 URL 的 User-Agent；拒绝 429/503 等异常、不追索无限页。SFX 真实候选的语义匹配和音乐审美仍由导演实际听取后选择；入库许可证明不是自动认定所有权。运行时若 DNS 被代理至非公网地址必须阻塞，不变更防 SSRF 边界。Freesound 的 OAuth/商用 API 作为独立的后续条件，当前没有注册或启用。

<!-- 旧路径章节锚点兼容；现行正文以本页内容为准。 -->
<a id="4-验收与未决"></a>
<a id="s6-15-g1--素材层架构与选型"></a>

<!-- 旧章节链接兼容；按现行正文与指向的历史来源阅读。 -->
<a id="5-来源扩展架构待实施"></a>
<a id="音频自动来源具体落点已实施软件真实下载待验收"></a>
