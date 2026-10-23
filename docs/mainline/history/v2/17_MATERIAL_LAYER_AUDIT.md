# S6-15 G0 · 五类素材上下游审计

> **HISTORICAL — 原阶段记录/研究，保留当时结论，不表示当前部署、授权或待办。** 当前入口见[主线导航](../../INDEX.md)。

状态：**AUDITED_BASELINE**。固定审计 `codex/s6-production@09fd994525eeef7d5bcef5c34ae090f379d16fb7`。用户本轮已授权审计、架构选型和实施；修复结果另记 S6-15，不把设计倒写为基线事实。原配置、素材及数据库不改不删，S6-14 真实生产继续暂停。

## 1. 目标与证据

目标仍是同一六维画像、冻结导演风格、不同内容下的自主且风格稳定的视频创作。对图片、视频、BGM、AI旁白、SFX分别检查：上游表达→冻结上下文→供料→身份/权益→编辑绑定→渲染→QC。已读正式需求、实施合同与实际源码，并用只读SQLite核查本地素材记录；没有调用真实供应商。此前355个生产测试及80个前端测试不是本次修复的验收。官方上游本轮核对仍 `b29d0d72d7988c7fbacd9f8c6c793c596e4854f9`，未合入。

正式边界文件基线 SHA-256：
- `easel/production/contracts.py`：`40d1ac34faf4d85c9a8b82647fd997340eff9b226ff8cdf68f0c992b732ff66c`
- `easel/production/editors/base.py`：`de7815360cee428d70c26e8f437d06843376ed8e5d56728cf17aa3dd48c44cfe`
- `easel/production/operations.py`：`63e0767ef5d36b47e735656764d78ae8ac7dd8b1613118aaf4f68a03e6b0d1be`

## 2. 五类素材矩阵

| 类别 | 上游与供应的实际情况 | 下游实际情况 | 结论 |
|---|---|---|---|
| 图片 | Scene.visual/required_input_ids；本地、Pexels/Pixabay、受控MiniMax IMAGE | asset_ids→CreativeEdit.scenes→图片运动/裁剪/FFmpeg | 主链接通，但Need未完整投影冻结意图 |
| 视频 | 与图片共用场景；本地、Pexels/Pixabay；生成型号/权益未齐 | 真实时长、source_start、原声保护，禁止隐式循环/冻结 | 主链接通，但无差别检索两种视觉类型，缺有界导演路由 |
| BGM | audio_mode=music/mixed；_acquire_music取合格音频再reviewed_public | AudioClip(role=music)的时间/增益/淡入淡出/显式循环 | 有链路，但缺音乐/音效用途区分和完整音乐意图 |
| AI旁白 | scene.narration+VoiceIdentity；VoiceTasks独立Operation/句段缓存 | 实际句段时长、顺序、不可截断/静音和字幕 | 软件整链已实现；真实音色目录缺失，通用HTTP协议不兼容MiniMax原生T2A |
| SFX | 素材域有SfxNeedSpec，但没有_acquire_sfx或等价供料路径 | AudioClip已支持sfx及时间/混音 | 断点是已确认创意→声效Need→供料→事件绑定，不是FFmpeg不支持 |

QC已有完整视频分段提交与全片综合，但历史测试基于合成媒体和模拟模型，不证明真实声音/审美/音效适配。

## 3. 缺口台账

| ID/优先级 | 基线证据 | 影响与处理方向 |
|---|---|---|
| ML-01/P0 | supply_tasks.py:63-65,164-168,318-321，Need仅scene.visual，UseContext无冻结限制 | 完整上下文投影；由导演生成有界检索意图，程序不发明导演风格 |
| ML-02/P0 | _allowed_providers仅按配置/媒体类型，未查本方案服务白名单 | production需plan-bound grant筛选外部来源；合法本地复用不依赖远程授权 |
| ML-03/P0 | supply只做visual+music；editors/base.py:71-89已支持sfx | 保留Plan/Edit公共schema，补内部声效意图、供应与事件绑定 |
| ML-04/P0 | _register同素材共享ID，但candidate_role单值可能覆盖；复核确认record_usage已有need_ids合并，无须重写该逻辑 | 分离实体/合法来源记录/用途；metadata持久绑定列表，多次使用不复制字节 |
| ML-05/P0 | CreationTasks.assets:40-48只验证作品/类型/文件；render沿用 | edit前、选中后、render前重验catalog、Rights、作用域和引用，备用可用不能掩盖选中失格 |
| ML-06/P0 | creation.py:80-117,135-149把所有候选作为工程依赖和credits | 候选不等于实际使用；只投影选中素材及字体，保留未用候选但不伪称已用于成片 |
| ML-07/纠正 | SQLite只读：两记录同source/scope/SHA，唯一区别是attribution_text，仅一条含来源链接 | 撤销直接清重推断；这是证据版本区别，保留两逻辑记录/一物理对象 |
| ML-08/P1 | semantic_index先排名截断，再Rights重验 | 失格旧记录可挤占合格新版；资格过滤在最终截断前，只对合格候选去重 |
| ML-09/P0 | application/supply.py:75-96先下载后查Rights；新搜索会重复下载同源资产 | 下载前拒绝已知不合格，来源/许可一致的本地字节复用，不能按SHA合并权益 |
| ML-10/P0 | RecordedModelTransport按task+ordinal定位，每个新runner从1开始 | 新内部语义任务需稳定用途namespace；旧默认操作ID不变，防恢复串回执 |
| ML-11/P1 | configuration.py以bool(voices)宣称声音可用 | 共用实际配置校验；缺Key、未知engine、无可用voice不标可用 |
| ML-12/P0 | Pixabay使用per_page=limit、query≤300；官方要求per_page≥3、query≤100；文档只图/视频；Unsplash所有API图像用途要求热链 | 修正参数，不臆造音频API；不把增加tracking单独等同离线生产合规 |
| ML-13/P0 | MiniMax原生T2A JSON/hex，当前Speech adapter期望二进制 | 显式协议适配，复用句段/Operation/回执/时长验证，不自动换声或补授权 |

### 已识别但本轮不隐式改变的公共边界差异

正式 `PlanDocument.Scene.id` 沿用 `Identifier`（最多128字符），现有 `editors/base.py:46` 的 `Scene.scene_id` 最多96字符，属于本轮之前已经存在的边界差异。素材内部投影现复用正式Identifier，不能为了迁就下游再缩窄上游范围。超过编辑器范围的方案仍需明确错误；未来若支持此极端范围，必须提出可追溯的内部映射或公共合同一致化方案，不以本轮文件SHA不变宣称所有上下游语义天然一致。对应测试仅证明内部投影不新增范围限制，不证明128字符ID已完成实际渲染。

## 4. 架构结论

保留SQLite/LangGraph/FFmpeg和作品权威，不恢复V1第二套协议。公共PlanDocument与现有EditProject/AudioClip不变；内部投影、用途绑定、供料授权和选材准入优先完善。旁白始终是固定文本/音色专用支路，不能作为任意音乐替代。软件通过不开放真实G4或S6-14。

## 5. 官方资料（2026-10-17读取）

- [Pixabay API](https://pixabay.com/api/docs/)：图/视频，q≤100、per_page=3～200、24h缓存；网页音乐分类不等于音频API。
- [Unsplash API Guidelines](https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines)：所有API图像用途热链、下载事件、摄影师/平台署名、非自动化高质量使用要求。当前不能据此证明本地FFmpeg自动供料合规，保留preview-only。
- [MiniMax synchronous T2A](https://platform.minimax.io/docs/api-reference/speech-t2a-http)：/v1/t2a_v2、明确voice_setting、非流式JSON/hex。
- [Freesound API overview](https://freesound.org/docs/api/overview.html)：原音下载与preview的权限/质量不同，新服务需账户与许可准备，不用预览冒称原音。

架构见[18_MATERIAL_LAYER_ARCHITECTURE.md](../../architecture/materials.md)，实施与验收见[S6-15](../tasks/S6-15_material-layer-hardening.md)。
