# Easel V2 · S4 需求差距与复用清单

状态：**COMPLETE — S4 源码差距基线；未实施。S5 期间按用户补充细化 G04 的过程可观察差距，架构另见 02_ARCHITECTURE。** 2026-10-16。

## 1. 任务与证据边界

- 用户授权：定稿 S4，结合 Easel 现有功能与 V1 实现，区分直接沿用、迁入和新增；暂不做架构设计。
- 权威需求：[S4 定稿](01_REQUIREMENTS.md)，V2-EXP-001～034。六维画像就是主人设，直接沿用，不能再建第二套主人设。
- Easel 业务基线：`8eeafb6b9bf62b26e2077057cbebe45721f5d464`。本轮位于独立 `codex/s4-product-requirements` 分支，仅修改文档。
- V1 只读基线：`easel-studio@57c8e2ade21af9fb6abccdab3f7ba8e50132314f`；下文 V1 链接均固定该提交。本轮实际读取素材库、复用、供应、权益、存储、导演风格及相关集成源码和部分测试，不只是读取设计文档；不是整个 V1 的穷尽审计。
- [S3 固定证据](https://github.com/webxia/Easel/blob/4a92247b071c31d37ed623327d8058e62c64037b/docs/v2/10_V1_LESSONS_AND_REQUIREMENT_INSIGHTS.md)用于校正历史验证范围。当前未运行模型、媒体生成、服务探测或 V1 生产测试，未迁代码、数据或凭证。
- “沿用”指保留已有入口或能力基础，不承诺零修改或完整需求已满足；“迁入”指用户指定的 V1 素材库相关实现，须适配与回归；其余 V1 代码只列可参考候选，不擅自扩大迁移授权。
- 文件/函数及测试存在仅说明代码证据；本轮未运行的测试不记 PASS。既有能力未覆盖的完整体验归入“新增/补齐”，不因存在相似名字而认领完成。

## 2. 可以直接沿用的 Easel 基础

| 项目 | 源码依据 | 沿用范围与剩余差距 |
|---|---|---|
| 六维画像就是主人设 | [persona.py](../../easel/persona.py)：`_FILE_ORDER`、`load_profile_text`、`persona_prefix`；[ProfilePage](../../web/frontend/src/components/ProfilePage.tsx)、[Web](../../web/app.py)画像读取/编辑入口 | 沿用六维文件、选择和编辑入口，不新增主人设。频道关联、默认导演与设置优先级需补齐；提示中的记忆范围声明仍须验证实际消费 |
| 聊天、附件与技能入口 | [Web](../../web/app.py)：`_chat`相关请求、会话附件清单及上传 API；[App](../../web/frontend/src/App.tsx)、[ChatPage](../../web/frontend/src/components/ChatPage.tsx) | 沿用输入、附件引用、对话和技能调用基础；作品级方案确认、必用/参考标记及制作状态不是已有聊天就能保证 |
| 文件内容库与媒体展示 | [OutputsPage](../../web/frontend/src/components/OutputsPage.tsx)、[Web](../../web/app.py)：`api_outputs`及输出路径处理 | 沿用文件浏览、媒体预览、下载和删除入口；当前 draft/ready/published 标签不是“用户接受了哪个视频版本”，需补作品版本和接受行为 |
| 媒体处理工具 | [合成器](../../skills/builtin/auto-short-video/scripts/assemble.py)、[TTS](../../skills/shared/scripts/tts.py)、[ASR](../../skills/shared/scripts/asr.py)、[音频工具](../../skills/shared/scripts/audio_ops.py)、[视频工具](../../skills/shared/scripts/video_ops.py) | 图/视频拼接、旁白/BGM、字幕、剪辑已有处理基础，可按适用功能沿用；没有据此证明 1～900 秒、四声音模式、自然音色或导演风格全部达标 |
| 已配置服务与本机 Web | [Web](../../web/app.py)模型配置和运行入口、现有技能菜单 | 沿用已有配置入口和非视频功能；不读出密钥，不更换服务，不将本轮声明作为真实调用授权 |

## 3. 从 V1 迁入的素材库实现范围

这是用户已指定的迁入方向；以下将其落实到已读源码。具体落地职责、接口、目录、数据库和调度方案不在本轮决定。

| 迁入项 | 已有实现证据 | 适配与验收边界 |
|---|---|---|
| M01 素材记录、入库、物理文件及作用域 | [library.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/library.py)：`LibraryScope`、`PromotionConsent`、`MaterialLibraryCatalog.promote_attempt_asset`；[store.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/store.py)：`AttemptMaterialStore`；[models.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/domain/models.py) | 已有内容摘要校验、文件大小核验、入库同意、作用域检索、来源及使用记录。旧 tenant/creator/Attempt 标识须与已有人设及新作品语义适配，不由此新增多人权限或第二套主人设；不搬历史库 |
| M02 历史检索、去重及复用 | [library_reuse.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/application/library_reuse.py)：`find_candidates`；[semantic_index.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/semantic_index.py)、[dedup.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/application/dedup.py) | 已检查作用域、文件可用性、当前作品限定、既往使用及当前用途；语义索引存在，但模型和索引资源需核查。复用结果只是候选，不能自动获得新授权或替换必用素材 |
| M03 库内优先、外部补料、供应不足 | [library_first.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/application/library_first.py)：`supply_need`；[routing.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/application/routing.py)、[supplemental.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/application/supplemental.py) | 先匹配库内候选，不足后有限外部回退，并隔离供应失败；生成路线单独返回，不在循环中直接生成。迁入后须兑现“必用→可用历史→新增外部→授权 AI”及停止条件 |
| M04 外部来源、获取、技术与权益检查 | [registry.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/providers/registry.py)、[acquisition.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/application/acquisition.py)、[inspector.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/application/inspector.py)、[rights.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/application/rights.py) | 现有 Provider 能力区分、重试边界、下载限制、媒体检查、来源证据和署名/用途判定可迁入。Provider 文件存在不证明当前可下载或已获用途许可；历史使用条件要重新核查 |
| M05 生成补料记录与观察复用 | [generation.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/application/generation.py)、[store.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/store.py)；[generation_modalities.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/materials/application/generation_modalities.py) | 生成资产接收、提交/观察记录与媒体检查有代码基础；实际供应商/模式未选定，配音不得混入生图/视频次数。保留“不明结果先查询”行为，不能搬旧计费口径或凭证 |

### 素材库迁入不是直接复制全部旧集成

[material_layer.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/integrations/material_layer.py)与[material_generation.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/integrations/material_generation.py)读取旧 creation、Attempt、Hypit workspace 和旧授权/报价流程；[material_supply.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/integrations/material_supply.py)把库目录、作用域和供应过程接入旧制作。上述依赖说明素材库有真实接入代码，也说明不能直接宣称复制即可工作。迁入须保持使用范围、来源/权益、文件身份、复用和生成计数边界；不预先决定沿用旧数据格式或整个执行流程。

已读测试覆盖点：[test_material_library.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/tests/test_material_library.py)包含入库摘要/作用域/重复入库/篡改拒绝；[test_material_library_reuse.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/tests/test_material_library_reuse.py)包含作品限定和复用重新审查；[test_material_library_first.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/tests/test_material_library_first.py)包含库内优先、有限回退和补料次数；[test_material_rights.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/tests/test_material_rights.py)包含未知/受限权益拒绝及署名。**本轮只读测试，未执行；迁入后须在 V2 重跑适配后的检查与真实制作。**

## 4. 需要新增或补齐的产品体验（完整需求映射）

每行列出最终需求与已读实现的差距。“新增”不表示底层必须全部重写；“V1 候选”不表示已批准迁入其架构。

| 编号 | 需求 V2-EXP | 已有基础及差距 | 分类 |
|---|---|---|---|
| G01 | 002、003、019、020 | 六维画像沿用；在已查 Easel UI/API 和 V1 风格入口未见符合需求的创作频道管理。需补一个画像多频道、频道与导演多对多、默认项和单片覆盖。现有 model channel/视频号不是本需求频道 | 新增频道体验 |
| G02 | 004、019 | Easel `BreakdownPage`将粘贴文本送模型，要求“结构套路/为什么会火/可复制模板”，输出可存选题；不是实际视频片段证据分析。V1 Creative Mode 有名称、版本和视听规则，但未证明“参考拆解→试片→接受保存”全链 | 新增导演形成流程，补齐旧拆解能力；V1 风格表达供参考 |
| G03 | 001、005 | 对话和原片设计表已有基础；需统一利用上下文、先给方向、摘要/脚本一致、一次确认与变更后的版本对应。原片 SDK 有设计表、预览两个固定检查点，不能机械照搬为每片必问 | 沿用入口，补齐确认体验 |
| G04 | 006、024、025、033 | 当前 Web 有 SSE 事件回放/停止/会话续接，它们不等于外部媒体任务恢复。V1 有 delivery/Attempt 流程，但历史真实案例仍有工程介入。需补用户确认后自主首版、作品级当前动作/步骤输入输出/决策摘要/成果预览/阻塞及恢复提示、取消、有界恢复和合法暂停；用户在 S5 补充强调可观察，既有 SSE 不证明完整展示已实现 | 补齐完整制作行为；旧调度仅参考 |
| G05 | 007、026 | Easel 有媒体编辑工具；V1 有保护声音/文字的局部修订检查。还需自然语言反馈与具体版本对应、改动影响/次数说明、新旧比较，真实验证未修改部分不漂移 | 补齐审阅与局部修改；V1 检查为参考候选 |
| G06 | 008、027 | 文件内容库可沿用；需作品/方案/导演版本/输出对应、明确接受、历史比较、再创作独立授权及引用保护。不能把 ready/published 或文件存在当作 Creator 接受 | 沿用内容库入口，补齐作品体验 |
| G07 | 009、022、023 | 合成器已有时长、画幅、可选旁白/BGM/字幕基础；原片流程另有入口。需按同版本样本验证三类输入、1～900 秒、两画幅、四声音模式、中文和字幕关闭；不能从可选参数推导全范围通过 | 补齐覆盖与真实验收 |
| G08 | 010 | TTS 有音色/语速与 SRT，字幕有 ASS 样式基础。需同文试听、实际画面预览、频道/画像默认、本片优先、音色不可用时明确替代选择及跨作品稳定性；现有缺配置回退说明不符合“固定音色不静默换” | 沿用处理工具，新增选择/保存体验 |
| G09 | 011 | 上传附件、主题短视频、原片包装均已有入口，但不是统一的混合输入制作体验；需明确必用/参考及保护原声、事实和观点 | 沿用输入工具，补齐输入约束 |
| G10 | 012、021、031 | 当前文件库不等于 V1 素材库；M01～M05提供已实现基础。迁入后需把来源顺序、允许复用范围、补料条件和权益证据接入实际创作 | 迁入素材库并补齐产品使用 |
| G11 | 013、026 | V1 `reserve_delivery_call`按 prepare/material/author/quality 记阶段调用，生成集成还依赖报价；不是用户确认的“仅生图/视频实际提交计次”。需按新语义计数、显示余额、追加授权并保证恢复不重置 | 新增/改造次数授权体验，不搬旧预算产品规则 |
| G12 | 014、015、016、017、018、030 | 媒体处理和历史 QC 有局部基础，S3 记录完整自主与跨题材风格未获普遍证明。需自检修复、待修预览/首版/接受区分、固定样本和四类结果独立记录 | 补齐验收与度量，不把历史通过追认 V2 |
| G13 | 028、029 | 沿用本机 Web、服务配置和既有功能；需检查新视频体验接入后的回归、能力缺失提示和不静默换服务 | 沿用并做回归验证 |
| G14 | 032 | 有模型/检索类技能入口，V1 有 script truth 相关代码；未证明公共事实来源日期、推测区分、个人事实保护贯穿方案与成片。需针对完整作品检验 | 补齐事实处理；旧事实检查仅参考 |
| G15 | 034 | 画像可选的消息入口已存在；需端到端验证无画像不借用其他记忆、方案建议、作品保存及后续归属不自动重做 | 沿用可选画像入口，补齐验证 |

## 5. V1 有实现，但本轮不直接决定迁入的内容

- 导演风格：[creative_mode.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/creative_mode.py)提供 `load_creative_mode`、名称/版本、按制作环节读取规则；[director-treatment.md](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/creative_modes/clear_memo_video/director-treatment.md)明确不强制 Hook/三幕/CTA。可参考风格表达与内容自由的处理，但不能据此宣布频道多对多、用户建导演及版本接受流程已完成，也不决定 V2 采用同样文件结构。
- 局部修订：[native_revision.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/integrations/hypit/native_revision.py)的 `assert_composition_preserves_sound_and_copy`等检查可用于理解保护范围；与 Hypit 文档/节点格式耦合，不预选制作引擎。
- 作品执行/授权：[creation_delivery.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/creation_delivery.py)存在调用记录、恢复与调度，[creation.py](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/easel/creation.py)提供旧作品流程；历史状态、锁、预算及 Attempt 不是本次自动批准的实现方案。
- S3 记录有被接受的历史作品，但自主完成曾 FAIL，跨题材风格 PARTIAL；不能以复制上述代码代替新版本验证。完整原片路径、长片和声音模式必须各自保留真实证据。

## 6. 验收与下一步

本轮完成条件：34 项需求有映射、迁入项有源码依据、相似名称未误认能力、需求状态与实测状态分离、文档检查通过。未开展迁移/生产测试，未新增架构图、接口设计、模块拆分、数据库或引擎选型。

后续在用户授权的阶段再处理具体实施和设计；当前交付的是 S4 定稿及差距清单。配置资源、真实样片、时长误差/音色标准、效率基线仍按需求文档后续实测部分准备，不回退为重新讨论已批准的产品目标。

### 本轮验证记录

- `python3 scripts/validate_document_paths.py`：1076 个路径、439 份文档/提示文件通过。
- 既有项目虚拟环境执行 `python -m pytest tests/test_document_paths.py -q`：10 passed；系统 Python 无 pytest，未安装新依赖。
- 需求映射核对：34/34；固定 SHA 文件引用 `git cat-file -e`：29 个通过。
- `git diff --check`：通过。V1 测试、真实供应商获取、生成与视频制作：未运行。
