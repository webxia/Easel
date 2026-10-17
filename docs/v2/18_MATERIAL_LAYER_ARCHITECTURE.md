# S6-15 G1 · 素材层架构与选型

状态：**IMPLEMENTED_SOFTWARE / REAL_SERVICE_VALIDATION_PENDING**。依据[五类素材审计](17_MATERIAL_LAYER_AUDIT.md)、[正式需求](01_REQUIREMENTS.md)、[唯一实施合同](15_IMPLEMENTATION_DESIGN.md)，按用户本轮授权进入实施。此文是内部设计，不代表运行验收，也不替代公共Plan/Editor/Operation合同。

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

## 4. 验收与未决

G0/G1为本轮审计和内部架构决定；G2/G3软件以实际执行结果记账。真实Provider、BGM/SFX实际库存与自然音色不足必须保持未测/阻断，**不自动开放G4或S6-14**。已有Keys不等于生产调用授权，Creator接受单独由用户决定。

不变文件：easel/production/contracts.py、editors/base.py、operations.py；不创建新的生产状态机。可修改内部Supply/Model调用命名空间/素材metadata/Provider/选材准入。不满足当前公共合同的新增要求必须单独提出影响分析，不隐式扩schema。官方技术依据见[审计§5](17_MATERIAL_LAYER_AUDIT.md)。