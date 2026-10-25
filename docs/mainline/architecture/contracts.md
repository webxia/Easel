# Easel 实施合同

状态：**已确认实施合同与带日期的演进依据**。本页定义约束；源码实现、部署和验收分别见实现导读、当前状态及具名Task。旧S5/S6标题/编号只保留追踪身份，不构成当前排程。

## 1. 复核结论与实施约束

历史设计取证基线（不是当前代码基线） `easel-v2-rebuild@8eeafb6b9bf62b26e2077057cbebe45721f5d464`；本次复核起点 `codex/s5-architecture@d25b8f8395c907180738a5795042c3fe86e6de0b`，两者 easel/web/skills/tests 无业务差异。V1 只读 `57c8e2ade21af9fb6abccdab3f7ba8e50132314f`。

- 现有 `web/app.py` 已有本机写入保护、画像/附件/outputs/聊天 SSE，应保留这些边界；V2 用独立 router 接入，不继续把全部新业务堆入大文件。
- 作品记录是业务权威；框架检查点、素材库内部记录不拥有第二套确认/额度。网络和数据库不能一笔事务提交，未知结果必须独立处理。
- 执行者所有权、工作发现、外部操作幂等、版本和事务事件属于 Easel；不能宣称引入图框架即可获得生产可靠性。
- 模型主链推荐程序控制的任务 API 和工具分发，无任意 shell、文件浏览或直接媒体凭证。既有通用 Harness 保留给已有聊天；只有证明满足同样限制的接入才可参与 V2 收费制作，不默认用完整聊天会话当创作执行状态。
- 编辑器已在 S6-09 落实为本地 FFmpeg 受限时间线，版本、许可、真实能力与未覆盖项见 [ADR-S6-009](decisions/ADR-S6-009-local-editor.md)及[选型依据 §5](../history/v2/14_TECHNOLOGY_SELECTION.md#5-编辑渲染本地-ffmpeg-与可编辑工程)。不整体迁入 V1 native_source/service，不把 Hypit 后续接入作为当前主线前置。缺失效果明确返回能力缺口，不得擅自改为效果降级的幻灯片交付。

## 2. 建议代码组织与唯一责任

所有路径相对受测 checkout；新目录/文件由对应实施任务创建。

| 目标模块 | 写入权与主要入口 | 不能负责 |
|---|---|---|
| `easel/production/contracts.py`、`errors.py` | Pydantic 业务输入/结果、版本常量、类型化错误 | 调模型/读真实凭证/隐式写库 |
| `easel/production/store.py`、`migrations/` | 作品/修订/授权/任务/操作/事件事务，文件索引 | 跨网络长事务、模型审美判断 |
| `easel/production/service.py` | 所有用户命令、版本核验、授权追加、接受/删除保护 | 把聊天 finish 当作品成功 |
| `easel/production/worker.py`、`graph.py` | 领取持久任务、阶段路由、恢复、取消、局部任务重建 | 自己维护另一套用户额度或原始用户要求 |
| `easel/production/context.py`、`model_tasks.py` | 必要上下文、能力检查、严格结果接收、受控工具循环 | 自动加载根 AGENTS/其他画像、任意 shell、直接付费网络 |
| `easel/production/operations.py`、`providers/` | 唯一提交/观察/接收与额度准入；Provider 错误分类 | 在重试装饰器里重新生成 |
| `easel/materials/`、`easel/production/materials.py` | 迁入 V1 库内能力与新作品适配；输出素材句柄 | 回写作品接受/方案、搬旧 Creation/Delivery |
| `easel/production/media.py`、`editors/`、`quality.py` | 音轨/字幕/工程/渲染/检测适配、局部保护 | 任意素材采购、改人设/事实、隐式更换音色 |
| `web/production_api.py`、`web/frontend/src/lib/productionApi.ts` | HTTP 合同、错误映射、快照/事件游标 | 复制执行状态或授权逻辑 |
| `web/frontend/src/components/ProductionPage.tsx` 等 | 输入/方案、制作进度、预览、审阅、版本比较 | 用前端内存或模型文本推测完成 |

工具尽量复用函数/API；独立脚本用参数数组与有限环境调用，禁用 shell 拼接。新作品文件开放前，S6-02必须同时改造旧 `/api/output`、`/api/media` 的读取、下载/打包及枚举入口，拒绝生产私有根和其符号链接别名；旧output与画像DELETE也要检查引用。不能靠隐藏目录名保护数据库，也不能留下rmtree/unlink旁路。删除聊天不得经stopChat隐式取消独立作品运行。

新模块只导入配置/存储接口，不从 `web/app.py` 反向导入，避免循环依赖与启动副作用。旧聊天和 V2 不互相创建第二个生产运行。

## 3. 数据与文件合同

### 3.1 存储布局

建议生产私有根 `outputs/_production/`，其中作品数据库、WAL、框架检查点、运行工作区和内部证据不直接映射静态下载。现有_safe_output_path只保证路径位于outputs，尚不能提供该保护；S6-02必须先封闭旧读取/打包/删除入口。用户可预览/导出的成片存 `outputs/works/<work_id>/...`，由受控媒体API仅放行已登记、允许展示且作用域正确的产物。上传入口产生经校验的input_id，绝不接受前端任意本机路径。

SQLite 开启 foreign_keys、明确 schema_version 和前向迁移；短写事务、有限 busy timeout，不在事务内等待模型/网络/渲染。备份必须覆盖有效数据库与 WAL 状态，先用 SQLite 在线备份而非随意复制单文件。应用初始化不能迁入 V1 用户库或扫描历史盘。

媒体写临时文件→核验内容/大小→原子落到稳定位置→登记引用。中断留下未登记文件时对账接收或保留待清理，不再次收费生成。数据库迁移失败停止 V2 写入并报告，不能破坏已有 Easel 聊天/文件入口。

### 3.2 最小记录与不变量

ID 使用程序生成的不透明标识；时间 UTC；数据库行有 revision 用于并发核验。JSON 内容必须有 schema_version，经合同校验；既有用户路径不作数据库主键。

| 记录 | 最少信息 | 关键约束 |
|---|---|---|
| channels | id、既有 profile_ref、name、定位/偏好、default_director_revision、音色/字幕默认、archived | 引用真实既有画像；不创建另一个主人设。删除/重命名画像不得静默切换他人画像；已有作品保留快照 |
| directors / director_revisions / channel_directors | 身份、名称、风格草稿/不可变版本、参考证据、style_confirmed、trial_pending、试片、接受记录、可用频道关系 | 多对多；默认必须属于有效搭配。接受作品与接受导演为独立命令，可在同一用户交互明确提交 |
| works / work_inputs | profile_ref 可空、channel_id 可空、当前方案/运行/接受版本引用、原始输入清单、必用/参考用途 | 无画像不得读其他画像。频道与画像一致；文件引用有作用域和来源，原片不可覆盖 |
| plan_revisions | work_id、revision、完整脚本/场景/设置/事实与禁止项/适配许可、画像和导演版本依据、hash、confirmed_at | 确认后不可原地改写。摘要是同一内容派生；scene_id 不使用 Markdown 行号 |
| authorization_grants | work_id、用途范围、所绑定input/preview/plan_revision、provider及model/mode允许清单、AI补料许可、IMAGE/VIDEO累计上限、明确收费/追加记录、撤销记录 | 生产授权绑定已确认方案；规划/试听只允许具名用途。追加不重置消耗；确认方案与生产授权同事务；新作品不继承旧授权 |
| runs / tasks | run_id、work_id、kind=planning/production/revision、目标输入/方案/编辑修订、graph_version、任务种类、依赖、input_fingerprint、结果引用、状态、owner_epoch | 同作品至多一个有效执行负责方；确认前规划也持久调度，确认后从冻结方案制作，不重复规划；局部修订新run并复用有效产物 |
| operations | operation_id、work/run/task、类型、input_hash、grant、provider/model/mode与配置版本、提交身份、Provider任务ID、状态、计数分类、回执摘要 | 同一个业务提交重放返回同一操作；用户明确新生成另建ID，不能仅按相同prompt去重。旁白/模型也留操作痕迹但不占IMAGE/VIDEO额度 |
| artifacts / artifact_edges | artifact_id、类型、hash、存储引用、来源/权益、方案/工程/模型/音色等依赖、检查结果引用 | 复用必须依赖相容且文件可用；单靠路径存在不算合格。保留版本仍引用的产物不可删除 |
| reviews / acceptances | 指定output_revision、用户意见、影响范围、修改授权、明确接受的时间/来源 | 修改不会抹掉旧接受记录；accepted_output_id 与当前run状态分开保存 |
| events / command_receipts | work_id、递增seq、run/revision、kind、实际payload、actor；idempotency_key及请求指纹 | 事件和领域状态同事务；同key不同内容409；重复请求返原回执，不触发新执行 |

以上是逻辑表族，不强制每个斜杠分成独立物理表。Coding 可以合并低复杂度表，但不能移除身份/版本/权限不变量；所有物理 schema 由 S6-01 在迁移文件中一次明确，后续不得各自另建同义表。

规划模型与试听发生在方案确认前：操作引用本次创作请求已明确的服务授权或具名试听授权，不要求先存在生产方案，也不因此获得IMAGE/VIDEO生成许可。已有授权范围内正常调用不逐次询问；新收费试听或未授权服务/模式按需求说明并确认。此为权限记录，不新增用户金额预算或配音次数额度。

### 3.3 状态机

- 作品展示：discussing / awaiting_confirmation / producing / needs_decision / preview_needs_fix / reviewable / cancelled。已接受是独立记录和UI标识，后续修改不能丢失历史接受。
- 任务：pending→running→succeeded；running 可进入 waiting_external / retryable_failed / needs_decision / failed / cancelled。恢复需核对当前版本、依赖及所有权，不能直接重放所有 running 项。
- 生成操作：reserved→sending→submitted→succeeded 或 failed_after_submit；sending 断线→unknown；可证明未提交→failed_before_submit 并释放预留。submitted 后失败仍计一次；unknown 保持待核实占用，不能作为已知提交或自动退款。
- 额度显示：已用=确认实际提交数，待核实=发送结果未知，临时预留单独记账；可用=上限−已用−未知占用−未发送预留，且不小于0。查询/下载/复用不增加提交次数。并发准入在一个短事务内完成。
- waiting_external 是在途服务任务；needs_decision 是授权/实质变更；retryable_failed 是可自动恢复的具体故障。展示断连不更改这些业务状态。

重复确认、防旧版本、取消和发送争用均由条件更新/唯一约束与command receipt保证。reserved→sending的同一条件更新必须核验当前run/task修订、owner_epoch、取消、服务模式权限与额度；过期执行者不能新建操作或发送。取消确认阻止新的sending；已跨发送边界的调用如实视为在途，接管者不得重发。过期worker不能登记当前版本产物，但可按既有operation_id递交不改变原请求的回执；程序核实后收存有效结果，保留收费成果。

## 4. 模块间接口与错误

函数名是实现合同，具体异步类型由实施卡落实；任务输入仅含必要字段和稳定引用。

| 接口 | 输入 → 输出 | 关键语义 |
|---|---|---|
| WorkService.command | command_id、work/revision、用户动作 → receipt、snapshot_cursor | 创建/确认/修改/取消/接受均走此入口；已有实体必须带expected_revision，创建时为空；版本不匹配409 |
| ModelTaskRunner.run | TaskContext、task_kind、能力要求、有限工具 → TypedResult/NeedDecision/TaskFailure | 不自写状态；有效结果校验后由调用方登记；格式纠正有界，保留原结果诊断 |
| MaterialSupply.supply | scope、SceneNeed、允许来源/用途 → candidates 或具体缺口 | 只有候选；导演检查实际媒体后选择，不由搜索顺序自动选片 |
| OperationService.submit/observe/receive | 已授权需求/operation_id → 操作事实、可用产物或unknown | 只有submit能发送新生成；observe/receive不扣新次数；所有恢复先读原记录 |
| EditorAdapter.check/build/observe/cancel | versioned EditProject、媒体句柄、允许能力 → 诊断、render_job、产物 | 不携带媒体生成凭证；输入禁止未经批准的外部URI/脚本资源。未就绪返回capability_unavailable |
| QualityService.inspect | 输出产物、目标规格/约束、视听证据 → findings | finding有位置、证据、严重性、影响范围；代码检查与模型判断分开 |
| RevisionPlanner.propose | 原输出、反馈、依赖 → ChangeSet | 明确受影响场景/声音/文字/额度及需确认项；程序依赖+模型语义影响共同决定，不只按文件diff |
| ProgressQuery.snapshot/events | work_id、after_seq → 状态/成果/关键事件 | snapshot附cursor；客户端用cursor续订，事件去重并忽略旧run更新 |

统一错误 envelope：code、user_message、retryable、affected_ids、operation_id 可空、requires_decision、诊断引用。code 至少区分 invalid_input / stale_revision / permission_missing / quota_exhausted / result_unknown / material_unavailable / provider_unavailable / invalid_model_output / invalid_edit_project / quality_blocked / internal_error。禁止原始异常/响应正文泄露凭证；retryable 不直接授权重复提交。

HTTP 约定：400格式，404不可见/不存在，409版本/命令key冲突，422业务约束/能力缺口，202已接收后台命令；401/403沿用实际本机权限规则，不能另造不生效的多用户认证。所有写路由仍经过 existing local_write_guard；读媒体仍有输出路径和作用域校验。

### 4.1 HTTP API 合同

统一新增前缀 `/api/production`，交互继续由现有 Web 入口调用。

| 路由族 | 作用 |
|---|---|
| GET/POST `/channels`，PATCH `/channels/{id}` | 列表/创建/编辑/归档及默认；关联既有画像，不绑定平台账号 |
| GET/POST `/directors`，PATCH `/directors/{id}`，POST `.../revisions`，POST `.../accept` | 名称/归档与风格版本分开；参考→草稿→试片→明确接受；频道PATCH可清除失效默认 |
| GET/POST `/works`，GET `/works/{id}`，POST `.../inputs` | 作品列表含未出片/无画像作品，按状态/画像/频道筛选并以稳定游标分页；建作品、输入和快照不依赖聊天存在 |
| POST `.../plans`，POST `.../plans/{revision}/confirm` | generate建立planning run；用户明确编辑直接产生新方案修订；确认含plan_hash/授权/command_id并只创建一个production run |
| POST `.../authorization-grants`，POST `.../cancel`，POST `.../resume` | 追加/取消/解决needs_decision；resume指定解决的decision及版本，不是无条件重跑 |
| POST `.../revisions`，POST `.../outputs/{id}/accept` | 自然语言意见生成局部ChangeSet，按影响处理；接受明确输出 |
| GET `.../events?after=seq`，GET `.../artifacts`，GET `/artifacts/{id}/content` | SSE事件、成果列表和受控媒体预览；缺失cursor历史可回快照 |
| POST `.../fork`，POST `.../assignment` | 基于旧作建新作品但不复制授权；只改归属不触发重做或扩大素材权限 |
| POST `.../voice-previews`，POST `.../subtitle-previews` | 同文音色试听与真实画面字幕预览；显式保存到本片/频道/画像，试听收费遵守授权 |
| POST `.../deletion-preview`，POST `.../delete`（目标作品/输出版本），DELETE `/artifacts/{id}` | 先给精确影响和版本指纹，用户明确删除后只解除授权范围的保留引用；直接删被引用artifact仍409 |

各任务只实现其负责路由；不要先把整个API注册为空壳返回成功。当前聊天发送接口不自动变付费视频创建：用户明确视频创作意图后建立/关联 work_id，后续消息可路由到该作品；自由聊天继续原行为。

## 5. worker、模型、素材与编辑主线

### 5.1 worker 与持久编排

CLI 目标增加 `easel production worker` 和 `easel production status`；启动 V2 Web 时启用受管理worker，关闭浏览器不停止它。Web服务退出可停止本机worker并持久保存，重启后恢复；不承诺电脑/服务关机期间继续运行。显式作品取消与服务退出是不同操作。

初期一个本机worker，可在已授权任务范围内有界并发；不用 Redis/Celery。worker用数据库owner_epoch/lease领取；heartbeat只是存活线索，过期回收必须递增epoch，旧写入拒绝。进程环境不继承全部用户密钥，按适配器必要字段注入。

LangGraph节点按产物边界组织。planning run：prepare_context→plan，写不可变候选方案后结束，作品awaiting_confirmation；用户确认后另建production run：读取冻结方案→supply/select→edit→render→inspect→review，不再调用plan改写已确认内容。revision run只包含ChangeSet影响的任务。首次规划、改方案和制作中修改均有输入版本及持久任务；planning不允许生成媒体，输入改变时旧结果保留但不得覆盖当前方案。

失败返回明确子范围，生成submit不是可无条件重试的整个节点。持久run记录graph_version，重启先对账operations，恢复有效检查点；旧图版本无法安全解释时停为可诊断状态，不静默跳节点。领域记录已提交而checkpoint未提交时幂等返回已有结果；反向窗口也重新核对，不能信任checkpoint覆盖已取消授权。

### 5.2 模型与工具

V1全局Voice生成只绑定完整脚本，不能直接承担句级修改；音轨按可定位段保存文本摘要/voice身份和边界，复用未改段并复查拼接听感。

首期不要强制多Agent；相同导演规则可覆盖多个任务角色。context不从普通长会话回忆授权，也不自动拼接根AGENTS/全量history。schema/prompt有版本；输出只需创意内容、引用ID和理由，既有身份、hash及权限由程序绑定。

能力配置分别说明文本/图像/音频/视频/工具/结构化结果是否真的可用。缺必要模态返回capability_unavailable，不用抽帧冒充完整视听检查。模型调用和TTS的实际费用仍需用户授权；虽然不计IMAGE/VIDEO额度，也不能无限重试。无效输出有限格式修正；无新证据循环停止，具体上限配置可调且记录本run值，不作为新增用户额度。

可用工具白名单：查询可访问素材、查看媒体证据、读取当前工程、提出生成需求、提交受控编辑、获取操作/渲染结果。工具执行都经程序校验作用域与授权；模型本身没有通用shell或媒体Provider凭证。任何下载外部文本/参考视频的内容作为数据，不作为权限或系统指令。

编辑及局部修订任务通过既有ModelTaskRunner提供只读inspect_media工具：仅接受当前已准入视频句柄与最多8个源片时间点，回传实际画面及时间证据；路径由程序解析，不接受模型路径、URL或生成指令。工具结果以程序类型与普通JSON结果区分，必要图像能力在下一次调用前校验。沿用每任务最多6轮、每轮最多8次工具、重复请求停止和逐次Operation授权，不新建Agent或任意执行入口。没有工具能力的服务仍使用显式抽样，不假称已复查。

### 5.3 素材与渲染

M01/02把LibraryVisibility（本机拥有者/画像可见范围）与UseContext（当前work_id和用途）分开，不能用work_id把所有库资产锁为单作品。明确可复用的同画像资产可跨作品复用，current_creation_only仍绑定源作品；无画像输入默认仅本作品，后续归类不自动扩大权限。M03/04检索/获取，M05通过OperationService准入观察。不迁V1用户库，不把旧rights结果无条件用于新用途；署名/版权证据进入最终依赖。V1测试适配路径/fixtures并保留负例意图，不复制PASS数字。

S6-07分别实现IMAGE和VIDEO的适配与能力声明，S6-10实现VOICE。未配置真实服务可先做离线协议测试，但缺失模态保持capability_unavailable/NOT_TESTED；一个生图adapter通过不表示生视频已接通。S6-09已完成本地 FFmpeg 首个编辑器决定及真实合成媒体证据，范围见 [ADR-S6-009](decisions/ADR-S6-009-local-editor.md)；S6-14继续验收完整生产能力，不暗含用样片代替未实现功能。

EditProject 保存编辑器类型/版本、可编辑工程、稳定scene_id、实际媒体依赖、音色与字幕生效值。当前 `ffmpeg-timeline-v1` 是该后端自己的受限时间线，支持实际视频剪辑/溶解、图片显式运动、独立原声/配音/音乐、固定字幕；不是要求其他引擎服从的通用视觉DSL。项目/manifest/结果hash与无字幕合成底片保留供修订和真实预览。未来更换引擎须按实际能力适配，不能跨引擎偷偷丢风格特征。

原声必用区间与生成旁白分开轨道/依赖。固定voice provider/model/voice_id及相关可用参数，缺失不静默换。字幕对实际音轨对齐并结合实际画面预览；字号是对应输出分辨率的可调整参数。当前 assemble.py 会保留显式镜头时长、缺省时借旁白推导；其默认静音/补帧及缺字幕回退需在适配时显式处理，不能照搬为产品限制。

2026-10-19 A10增量：未指定长度的新自主旁白方案在确认前由原生模型复核具体分析和可执行画面，并冻结`narration_policy`。`continuous=true`按完整段落生成语音，保留逐字内容、稳定片段身份和真实音频；镜头可以跨越语句切换。`duration_mode=voice_driven`用于未指定精确长度、无受保护原声的voice/mixed作品；BGM不改变时长策略；冻结草稿长度为估计，执行工程按完整语音实测长度编排，保存`execution_timing`及voice_schedule，不能插入数秒空白凑估计片长。精确指定片长、旧方案、原声及固定时间音效保持原规则；不挤压、截短或加速已有音频。局部修订及QC以实际工程长度为依据，不改历史Plan/hash。

MiniMax原生适配可显式传支持模型的emotion及subtitle_enable；导演风格文字不冒充通用TTS instructions。情绪不强设为某一种；2.6专属选项不用于2.8。供应商字幕仅在HTTPS白名单、无鉴权外泄、大小与时序校验和完整逐字覆盖通过后用于字幕。字幕下载失败保留收到的语音，不重发付费合成；模型预览字幕与真实对齐分开记录。音色身份及参数仍进入授权、缓存、方案及素材依赖；候选试听不自动改长期默认。


A10文字编译补正：CreativeCaption明确narration/overlay用途。频道字幕设置只编译旁白；解释文字保留模型所设计的独立几何/样式，不能一律压到底部。供应商字幕只替换旁白，不删除解释层。新自主时间线要求明确role，以真实字体和与导出共享的排版几何检查同时显示的文字碰撞，失败进入原生有界纠错；旧输入未声明role时仍按旁白处理。执行EditProject不扩展role合同，角色证据另保存在工程元数据。已知质量失败按同作品真实文件digest保护，包括同字节导出副本，不能换artifact_id绕过接受/重导出限制。

原生修复重剪的声音保护按实际完整AudioClip和原声使用检查，不能仅因静音镜头数量不同而误判音轨变化。模型方案成功收到但在后续程序检查被拦时，保留服务器记录的提案及producer_task_id；恢复先核对原输出digest和提案来源，旧版提案还须与同Task成功MODEL回执的类型化内容相等。复用原生提案且不覆盖原记录，不重新发送模型，也不回收或重发UNKNOWN；声音/原声/内容/几何保护仍完整执行。

A10原生图解增量：两轮真实视觉复核均证实，搜索到的相似物件无法表达模型已写定的具体数量、分类及条件变化。新增可选explainer_boards，由创作模型在冻结前自行定义卡片文字、类别、状态、强调项及状态中的类别重命名；程序只渲染字面数据、布局、真实数量与持续的概念/假设标识。不接受真实客户/个人事件数据的伪造证明、不执行任意HTML/SVG/脚本、不取外部图像。单组最多12卡/4类/4状态，每类最多5卡，文字长度与引用有界；当前仅支持概念或假设示意，底字幕/关闭字幕的16:9及9:16布局，非通用绘图引擎。

能力以实际已配置字体为准并公开到local_visuals；缺字体不可自称可用。本地PNG以冻结数据、渲染器版本、字体hash和画幅为来源，进入既有素材登记/技术检查/本片引用与保留链，原始文本依据仍为已确认方案；不调用生图服务、不消耗IMAGE/VIDEO次数，不复制第三方图库使用权。图解不是其他场景的通用库存；原生MaterialIntent通过board_id/board_state_indexes明确各叙事场景引用的图解及状态，程序校验真实引用、完整状态覆盖及首次出现次序。允许同组图解跨段复用、回看和局部特写，不硬性要求每态全幅或禁用所有补充标注；必要类别、数量、标识及关系是否可理解由实际画面审查，图层碰撞仍检查，不能把图解定义所在scene_id误当排他使用边界。旁白字幕继续使用频道样式，原生视觉修复不能擅改其透明背景；独立解释层另行布局。图解与实景比例由导演按内容选择，程序不替模型写本片例子或创作观点。

供应商字幕定位与配音分开恢复：临时文件定位只留受管私有provider缓存，不返回到素材元数据/日志或导出，诊断只含主机。后续观察可只读补取已获准HTTPS主机的字幕，音频hash、声线身份、原成功Operation保持不变，不因字幕下载/准入失败重复合成；不会读取HTTP/本地主机或把临时签名当作公共来源。

A10字幕时间增量：准入已在实际语音回执观察到的MiniMax字幕CDN，仅匿名HTTPS只读下载，不跟重定向、不导出签名地址，不重发TTS。可选EASEL_VOICE_ALIGNMENT_MODEL=base/tiny/small，使用本机已缓存faster-whisper模型，将已确认的原文字面强制对齐到同一音频、且限定在提供商段落锚点内；禁下载模型、不做转录替换、不改变声音字节。内部时间标记为local_acoustic_forced_alignment/estimated，而非提供商精确字时。按标点/长度将原文字面组合为短字幕，保留真实提供商锚点及音频hash；不可用则保留提供商结果，不因字幕失败再付费合成。

A10归帧修正：原生镜头累计边界先量化到最近视频帧，再导出各段帧长，不能独立舍入每段导致累计漂移后错误拒绝正确总长。每个累计边界误差不超过半帧，镜头身份/顺序/起点/转场类型和音轨不变；不足一帧而坍缩的镜头仍阻断。精确总长与源素材可用范围继续由编辑器检查，不增减镜头或用末尾补时兜底。

A10模型合同自描述：BoardState的groups键/值显式使用同一Identifier类型，schema直接声明每列最多5项、每态列出所有columns.id（不是title），空列仍保留；highlight_ids/column_titles同样引用真实ID。该调整把既有运行时约束放进可见schema，不改变有效历史Plan集合或降低数量/引用检查。草稿审查前先执行固定设置保护，原生审查不能批准错误声音，设置差异作为原生草稿修正输入处理。

字幕可显式设置`single_line=true`：仅口播字幕按真实导出字体和可用宽度分页，长句依次显示、不同时换行，不改独立解释层的字号与排版。每条原字幕的首尾锚点保留；超宽字幕内部按字面长度分配的时间仅为布局估计，另记`subtitle_layout`，不冒充供应商字级或声学对齐。预览和草稿样例采用同一分页函数；静态预览明确返回实际首条文字及分页数量。未启用时沿用原排版，并省略新增默认字段以保护历史方案指纹。文字图层碰撞检查不能识别素材像素中烧录的字幕，后者由导演依据实际画面选段、构图和审片处理，不以图层检查通过代替成片核验。

## 6. 质量、局部修订与用户可观察性

草稿、视觉和完整视听审查分别记录findings（有证据的必须修复问题）、suggestions（非阻断建议）和limitations（观察边界）。findings应指出内容/明确要求与证据，不因可选审美建议返回fail；旧findings及失败回执保留阻断含义，不在升级时自动降级。草稿尚无素材或声音不属于已证实成片缺陷；草稿无findings时不因裸fail标签重写。manual抽样无findings时保留原始verdict、建议及观察局限，semantic记not_tested并交人工审片，不触发自动重剪；完整视听覆盖不足仍为partial。个人感悟不强制案例、教学结构、结论或升华。

A10实际重跑进一步暴露“高分辨率的无关示意也能被manual模式交付”。显式启用`EASEL_PRODUCTION_VISUAL_REVIEW=1`后，新自主方案在manual审片模式下增加实际带时间抽帧的独立视觉复核。复用semantic记录，rule_version=`visual-preview-1`，scope=`sampled_visual_only`，通过抽样仍记semantic not_tested，不冒充连续动作/音频/全片语义通过；已有具名视觉缺陷及历史fail/partial记录不能被后来的manual记录或只重新导出绕过。具名视觉问题可进入既有原生局部修订一次，保留完整AudioClip与声音资产，仅有界补库存；反馈来自复核模型，外围不手写镜头替换。修订后再次复核仍失败则保留preview_needs_fix，不无限重做或降低标准。不增加数据库迁移。

仅该原生复核触发、且有narration_policy的修复允许原场景拆为`原ID-cutN`镜头；原叙事顺序、实际净总长、全片规格、完整AudioClip、原字幕字句/时序均受程序保护；允许相邻镜头组重新分配时长。新增提示字只能逐字取自冻结visual内明确引号标注的短语，不新增事实、观点或口播。普通用户局部修订保持既有assert_local_revision约束，不普遍放宽保护；含原声镜头可作裁切、适配、运动等纯画面修改；素材、取源起点、时长、增益及按scene_starts计算的声音位置保持，不能借视觉修复移动、删除或新增原声。

A10草稿闭环增量：真实后期复核证明，已冻结图解的分类语义错误不能靠换镜头修正。因此无固定片长的旁白自主规划在冻结前独立审查具体论证、图解分类及视觉策略。实际已配置字体先渲染草稿各状态，支持image的创作模型收到真实PNG与完整结构；无image时明示仅文字审查，不假称已看图。发现明确问题时仅原生创作模型修正完整草稿并再次审查，最多两轮草稿修正，逐轮保留审查记录与真实证据；仍失败保留原回执并停在冻结/TTS之前。程序检查字面引用、几何和已选声音/字幕等设置，语义判断仍归模型，不写本片分类特例、不降低用户隐私约束或要求额外人工改稿。

草稿像素审查同时使用固定字幕样式与同场景原文前缀构成实际排版样例，调用与正式导出相同的caption_from_settings/caption_layout/caption_image。原图解hash保持独立，样例合成只作预审、不注册为成片素材，清楚标记非最终断句/时码并附实际文字边界；不能仅因页脚和字幕均在底部就推断发生碰撞，正式剪辑仍须检查全部实际字幕与图层。

草稿恢复使用Task私有checkpoint与同Task/Work/服务配置的成功MODEL类型化回执逐字段/摘要验证；仅兼容已证实的旧原生修正回执，不能采用外部替换稿、跨任务回执或跳过reserved/sending/submitted/unknown请求。恢复保留既有回执原字节、审查历史与已用修正轮数，不重新发送最初作者请求，不借恢复增加修正预算。图解渲染器v2取消程序擅加的卡片序号，显式写在卡片原文中的数字仍原样显示，真实条数/分组标识保留；版本/字体/预览协议进入草稿预览路径，避免覆盖旧像素证据。

技术检查输出可解码、音视频轨、时长/画幅、素材引用、字幕时间/范围及声音线索；语义检查基于真实视听证据核对事实、观点、风格、节奏。自动检测黑场/静音仅是线索，允许有意留白，不能为PASS删除创作。

质量记录绑定精确artifact hash与检查规则/模型版本。待修候选不能成为reviewable；新输出不能沿用旧输出PASS。机器合格和用户接受分开。审美改进建议不自动变无限阻断；缺必用内容、错误事实、不可播放等属于阻断。

RevisionPlanner输出ChangeSet：base_output、affected_scene_ids、changed_audio/text/settings、expected_new_image/video_calls、scope_expansion、new_permissions、reusable_artifacts。用户清楚授权的局部低影响修改无需二次审批；扩大范围/新增生成说明随修改确认，额度不够再追加。active run期间的新修改先形成请求，不改写正在消费的P1；确需重定向则停止新派发并保留在途结果，创建新修订/run后重算依赖。

**A8局部修订实际合同补正（2026-10-19）：** `POST works/{id}/revisions` 可显式传`preserve_audio`布尔值（旧请求缺省false；Web默认勾选保留声音），持久到修订task。该选项为true时，程序比较全部AudioClip及场景原声开关/增益，任何改动均阻断；不调度TTS。固定所选输出及同方案最多32个既有视觉候选后才调用模型，恢复不改变已发送请求指纹。RevisionProposal可提出最多4个已确认scene的`material_searches`（复用VisualIntent，每项候选最多4），仅执行一次有限库存检索，复用原Supply的授权、Rights、下载/入库/引用校验并排除本轮已观察不合用的原候选；结果持久化。后续选择使用独立MODEL命名空间，重复/UNKNOWN仍按原Operation规则处理。不重跑Planning或全片Supply，不进入AI生成。替换静音画面允许选定新素材及source_start，原声音和场景时间结构保持不变；未选素材不进入新工程依赖。

同一`revisions`命令可显式传严格布尔`render_only=true`，绑定选定输出及其不可变已登记EditProject、同Work/已确认Plan和实际依赖；创建revision Run后首任务为render，跳过修订MODEL/素材/TTS，不接受客户端工程或路径。旧工程含PENDING_VISUAL_MATCH或该输出已有semantic fail/partial时拒绝纯导出；活动Run及命令幂等/版本守卫沿用原合同。QC仍遵循正式配置，本轮manual_review_only因此重新导出无MODEL，不以此声称语义PASS。Web每版本提供“只重新导出此版本”，产生新输出并保留原版/接受选择。字幕合成对已固定尺寸/像素格式的montage禁用FFmpeg滤镜图重建，防止切换素材色彩标签丢失后续字幕；真实编码测试覆盖跨标签、多段及空白间隔。


模型缺audio能力时，局部画面/字幕修订可用真实帧并按程序保护已有音频，不声称听过；完整语义QC要求不变。CreativeEdit新增只用于决策的`unresolved_scene_ids`（不编入EditProject）；导演明确缺关键画面或保留旧`PENDING_VISUAL_MATCH`标记时在渲染前阻断，不能将其降格为普通备注。素材搜索仍只返回候选，程序不替模型判断动作/风格是否匹配。明确给出的Pexels具体视频页可作为VisualIntent.query（options=1）：供应器只路由已授权Pexels，严格匹配规范HTTPS页提取数字ID，调用固定官方API取回该ID；拒绝任意URL、凭证/查询/fragment或错ID回执，复用原许可、域名、下载、入库与引用校验。具体页模式优先高分辨率MP4，不沿用API任意的SD优先排序。

进度概览持续显示阶段/具体动作、并行任务、成果预览、消耗/待核实、阻塞及下一步；展开输入/输出和面向用户的选择摘要，不暴露模型内部思维或凭证。事件至少包括 command_accepted、task_started、artifact_registered、operation_waiting、decision_required、revision_created、quality_result、run_completed/cancelled。模型token流不是业务事件真相；长期无更新显示最后时间/状态待核实，不模拟百分比。

<a id="natural-expression-design"></a>

### 6.1 通用自然表达能力（去 AI 味，本期实现）

自然表达的产品职责与规则冻结合同见本节；既有任务不补标/迁移的适用范围见§6.1.3。2026-10-22的软件、部署、停止制作及清晰度延期决定均为历史轮次记录，不作为当前授权或能力判定；演绎和编码的后续合同见本页末节，最新验收见[状态](../project/status.md)。

**V2.1 / CRE-01实现增量（2026-10-25，已合入V2；运行状态见CRE-01）**：仅执行当前`natural-expression-4`规则格式及`editor-context-2`编辑视图；保留core/write/visual/review四片段，不增加审核轮次。当前任务的规则正文与摘要冻结，不受之后默认正文变化影响；非当前版本或缺少规则的历史任务在模型调用前停止，提示重新规划，不自动升级、恢复或重发。历史成果和记录保留查看。

编辑上下文统一使用`TaskContext.model_data()`投影，`creative_data()`及fingerprint仍保留原始语义。首版编辑和局部修订传完整素材元数据；不再存在旧版白名单、旧编辑视图、旧格式修正请求或检查点机制前的推断恢复入口。成功回执、UNKNOWN保护和当前native_draft_checkpoint恢复不变。

视图在已知`use_constraints`和`material_uses[].need.constraints`路径，对相同且值得共享的完整字典建立共享表，每处引用保留原作用域；与顶层完全相同的director引用`/director`，不同导演或未知路径保留。相同画像快照引用`/profile`，content_hash保留。Rights、图解状态、声音事件时基、实测音轨、观察范围及未知字段不删。记录视图版本与原始字符规模，不把字符数等同Token；减少重复不证明真实表达效果。具体测试及使用边界见CRE-01。

#### 6.1.1 采用方案与取舍

采用**一份通用规则源，结合原有导演与本片依据，按既有任务装配**。将规则复制到每位导演会导致漏用、漂移及无意义的导演升级；独立润色 Agent 或配音后的自动改稿会增加调用和依赖失效，因此本期不采用。无需新增功能开关、制作节点、业务表或用户确认关卡；能力在部署后默认参与新创作；离线检查不替代真实自然度审阅。

规则由产品代码中的受信来源维护，复用 `context.py` / `model_tasks.py` 的任务装配边界；不在运行时下载第三方 Skill，不加载仓库研发 AGENTS，不把整套外部提示词或用户参考文本提升为系统指令。通用原则只维护一份，各任务取相关内容，不能在规划和审片里各自发展不同的“去 AI 味标准”。讨论阶段只解释及收集创作意图，不因讨论自然度发起新模型生产任务。

**最小实现形态**：一个小型纯函数规则模块，内容为共用原则及 `write / visual / review` 三种短片段；既有调用点显式选择片段，`ModelTaskRunner.run` 增加一个可选内部参数即可，未选择的调用不注入。这个参数是提示内容选择，不是新增工作流节点。不要按现有中文 `task_kind` 文本做关键词路由，不无差别改全局SYSTEM，不建设插件、可编辑规则后台或动态策略引擎。本期“通用”指V2视频生产内各导演、画像和既有可用路径共用，不扩展普通聊天及旧版视频技能。

事实、已确认观点、必用内容、固定声音/字幕与权限为保护项。自然表达的软性偏好须服从本片文体和明确风格：正式分析不强制聊天化，诗性表达不强制全变事实短句，有意的排比、反复、停留或快切不因形式被判失败。参考样本只用于节奏、措辞等风格校准；没有样本也可工作，不强制上传样本或重新确认画像。

#### 6.1.2 嵌入现有任务的设计落点

| 既有任务/入口 | 本期设计行为 | 保护边界 |
|---|---|---|
| 方案创作与内容修订：`planning.py` | 选择write片段，通用规则与完整六维画像（若选用）、导演、频道定位、本片内容共同输入；直接产出符合语境的文案和视听方案。提交结果前在同一次创作内核对含义及冗余，不输出思维过程或另建润色任务 | 定长/自主时长的新方案都接入；只允许改声音模式、逐字保护原稿的protected_plan路径不执行文案自然化；用户手工提交的方案不暗中重写 |
| 已有草稿审阅 | 在原有审阅调用中检查套话、推理、文体和事实漂移；能修的文案问题在冻结/TTS前处理 | 当前独立草稿审核仅覆盖特定自主旁白路径，不能写成所有路径已有审核；无独立审核的路径使用作者任务内自检与既有后续检查，不为本功能新增调用轮次 |
| 选材与编辑：`material_intent.py`、`creation.py`、`supply_tasks.py` | 选择visual片段；用现有场景描述、适配许可和选材理由区分“必须表达的意思/事实/动作”与“可替换的表现形式”；真实素材决定具体镜头与节奏 | 操作教学、事实证据不得用含糊示意替代；不以自然化绕过有实证的语义错配。被证明过度逐字配图的旧判据，按明确要求及实际证据重新判断，保留历史结论，不直接将旧失败改为通过；不新建素材Provider或无依据补料 |
| 配音：`voice_tasks.py`及既有适配器 | 朗读冻结的口播正文，使用已选声音及已支持参数；自然度先来自稿件与语义衔接，适用路径继续复用连续旁白能力 | 导演注释不进入朗读正文；风格文字不冒充供应商支持的演绎控制，本条保留固定声音与冻结正文保护；停顿编译等后续已确认扩展以末节演绎合同为准，不以早期“未新增参数”限制已批准能力 |
| 视觉/完整视听审查：`quality.py`、`creation.py` | 与已有草稿审阅一样选择review片段；结合导演意图和实际收到的证据，沿用 findings/suggestions/limitations | 不增加分数或 AI 检测器；manual/抽帧路径的声音自然度、连续动作与全片节奏由真人审片，不为本功能换模型或新增自动审核调用 |
| 用户局部修订：`revisions.py`及既有编辑路径 | 新方案的视觉局部修订用visual片段，只改获准部分；确需改口播/内容时复用既有“确认扩大范围→提出新版方案→确认生产”路径 | 不把局部改稿描写成已有的自动润色能力；本期不开发逐句改稿到配音/字幕的精细重算链。纯视觉修订不改文字、音轨、字幕时码或重跑TTS |

参考拆解仍描述实际观察到的风格，通用基线不删改参考片的特征/证据，也不将其缺点原样复制为所有作品的硬要求。纯查询、导出和技术检查不被扩成创意改写任务；既有无导演上下文得到通用基线，不借本功能修改三条管线的选择/确认合同。

#### 6.1.3 新任务的规则固定与恢复（不兼容旧任务）

通用规则版本与 Director revision 分开，仅保存一份可恢复的规则快照，不在每层另建版本体系。确定传递链为：**新规划任务的 `creation_basis.expression_policy` → 冻结Plan的 `conversation_basis.expression_policy` → `PlanningTasks.context` → 既有模型调用**。快照仅包含版本、摘要及上述有限规则文本，由程序生成/校验，冻结时覆盖模型或客户端提供的同名值。利用现有JSON字段，不新增Plan顶层字段、业务表或数据库迁移；不向频道/settings写未知键，不将管理元数据在模型输入中重复投影。

创建和冻结是同一份快照在两个生命周期位置的传递。`service.freeze_plan`须显式保留该字段，`planning.context`须从所选Plan读取；新方案内的制作、视觉修订及范围扩大后的新版规划沿用所选依据，不改读全局最新值。任务payload已进入现有任务指纹，实际规则文本已进入现有模型请求hash/回执，直接复用；不增加另一套请求账本。配音仍按原文本、声音及配置缓存，不将规则版本加入其缓存键。

启用后的新任务仍须支持正常中断恢复：使用自己的固定规则，复用成功回执，UNKNOWN不重发；不能因为默认规则文字变更而改变已发送请求。本快照只固定本功能的规则，**不承诺任意未来代码/schema版本的跨版本续跑**，也不建设历史提示词重建器。

既存任务/Plan无该标记时不自动补标、迁移、套新版或续跑；受影响的生产执行入口在付费提交前说明“不属于本期新任务支持范围”，不以当前默认值兜底。部署前仍须按既有规则核对在途工作，不擅自中断、取消或转换历史任务。旧数据、文件、接受记录和UNKNOWN按原保护保留，不删除；不为本功能新增历史恢复功能，也不借“不兼容”破坏既有只读查看。纯查询/技术重导出不进入自然化，既有安全校验保持。

#### 6.1.4 本期验收与停止条件

以下为待执行判据，不是新制作流程或真实通过记录。实施后的离线检查复用现有任务/保护测试；待后续制作获明确授权后，真实质量随一部实际作品审阅，不要求先完成跨题材、跨导演的付费作品矩阵。

| 验证点 | 必须观察到的结果 |
|---|---|
| 通用装配 | 启用后的不同导演、既有无导演上下文、定长/自主新方案与视觉修订使用同一基线及显式片段；参考分析、保护式重规划、手工稿和查询/导出不被润色；离线验证装配，不冒充模型效果 |
| 内容忠实 | 对含“可能/仅/不/计划”等限定的样本，以及引用、数字和第一人称样本，润色不新增、遗漏或强化主张；风格样本的经历不进入目标文本；语义效果须实际审读 |
| 风格保留 | 正式分析保留必要术语/推理，轻松讲述可自然转折，有意重复和诗性句子不机械删除；同一片段本已清楚时允许不修改 |
| 视听适配 | 示意能表达当前意思，明确操作/事实的必要信息仍准确；镜头停留、快切或留白有可解释用途，旁白不因逐句强强调或假语气词破坏理解；以实际所见/所听为证 |
| 无额外流程及保护 | 没有新增humanize节点、固定额外模型调用、评分、确认或重试额度；新任务冻结后的文字/音轨保护、成功结果复用、默认规则改变后的同任务恢复和UNKNOWN不重发有正反例；历史任务不补标/不自动派发，不要求旧任务兼容测试矩阵 |
| 真实接受 | 审片反馈指向具体句段或时间位置，核对自然度、可信度、可理解性与所选风格；SOFTWARE_PASS、REAL_PRODUCTION_PASS、CREATOR_ACCEPTED 分开记录 |

findings 必须说明具体内容/时间、实际证据、受损的事实/理解/明确要求；“像AI”、命中某词或句型本身不足以判fail。只有审美偏好、可选表达改善放 suggestions，未见/未听放 limitations；已确认影响用户接受的具体缺陷不能因“只是风格”藏入建议。沿既有有界修订处理，不追加独立自然化重试。实现通用接入并完成本期实际作品审阅后收口，跨作品稳定性与系统优化仍留 S7。

#### 6.1.5 开源依据与采用边界

2026-10-22 已只读对照以下项目源码；它们是设计参考，未安装、未运行效果评测，不以仓库热度、提示词自评或检测率证明成片效果。

| 参考 | 采用 | 不采用 |
|---|---|---|
| [Humanizer](https://github.com/blader/humanizer/blob/main/SKILL.md)（本次读取3.1.0） | 空泛铺垫、机械结构与重复总结的识别；样本文风匹配、事实保护 | 英文词表硬套中文，完整改写仪式或单独Agent |
| [Humanizer-zh](https://github.com/op7418/Humanizer-zh/blob/main/SKILL.md)（标注2026-09-23修订） | 保留信息/确定程度，尊重文体，模式只作线索，通顺内容可不改 | 将“去AI”解释为身份判断或检测器保证，强迫聊天化 |
| [Stop Slop](https://github.com/hardikpandya/stop-slop/blob/main/SKILL.md) | 减少无信息铺垫与口号，关注具体含义和节奏 | 全面禁副词/被动/问句、固定句长变化和35/50分数门槛 |

采用的是经筛选的原则，不声称这些文本技能已解决配音或视频自然度。实现时固化已审查规则及来源；若直接复用第三方内容，核对并保留其许可/署名，不自动跟随上游主分支。所有个人样本和运行证据继续留受管私有记录，不复制到通用规则或Git。

#### 6.1.6 可行性审查与实施收敛（2026-10-22）

历史问题、探针和当时实施收敛见[原合同§6.1.6](../history/v2/15_IMPLEMENTATION_DESIGN.md#616-可行性审查与实施收敛2026-10-22)。当前规则传递合同在§6.1.1～§6.1.4维护；后续改稿、演绎、编码扩展按本页末节，不受旧三块实施范围限制。

#### 6.1.7 本期实现与软件验收（2026-10-22）

实现过程与原测试数量见[S6-14A具名记录](../project/tasks/S6-14A_conversation-integration.md#natural-expression-implementation)，[整理前原文](../history/v2/15_IMPLEMENTATION_DESIGN.md#617-本期实现与软件验收2026-10-22)保留历史快照。此处不重复维护通过数量、部署指令或制作暂停状态。规则源、快照传递、缓存与恢复要求按§6.1.1～§6.1.4及末节版本补充执行；具体源码落点见[实现导读](overview.md)。

装配仍须显式选择任务角色，不凭task_kind中的关键词猜测；规则只进入系统提示，创作数据投影避免重复携带规则文本，但实际快照继续参与上下文指纹，防止跨规则复用素材意图缓存。参考拆解与受保护声音重规划的写作片段排除须有对应回归，不能用保留条件/否定的投影测试宣称模型输出已保证不漂移。

## 7. UI、默认与长期资产

沿用 ProfilePage/ChatPage/OutputsPage；新增频道/导演配置与作品页由现有App路由连接。必须可无画像无频道创建。频道表示系列，默认导演是已接受的版本；跨频道同风格不复制经历。

音色/字幕按本片→频道→画像解析并在方案确认时固定，后续修改默认只影响新方案。保存到长期默认须用户明确指定作用域，不能因为本片改字号就修改频道。正式首版兼试片时同时展示两个独立接受选项，不从“接受视频”推导“保存导演”。

根据画像/频道/本次风格推荐少量可用声音，支持同文试听及服务支持的语速/情绪参数。固定音色不可用时保留原设置，说明原因并列出替代试听及收费条件；用户明确选择后建立新本片设置，不静默更换或修改长期默认。导演归档后不再用于新作默认推荐；失效默认提示选择或明确取消，已确认作品仍固定原版本。

内容库展示作品选定输出并可比较历史版，保留已有文件浏览；不将旧ready/published标签当接受状态。新作品基于旧作品时引用允许素材，但新建方案与授权。画像或频道归档保留历史引用，不让同名新画像静默占用旧身份；具体重命名/删除通过引用检查或提示解除关联，已确认快照不回写修改。

LIB-01内容库按已接受作品、未接受创作和其他文件项目收纳；一个Work只展示一张首页卡，接受A后新增B仍默认A并提示未接受版本。原library接口默认scope与artifact_id语义保留，只追加更新时间及最新可展示版本摘要。轻量详情沿现有快照读取，浏览和版本选择不执行命令；继续创作沿原App入口建立关联同作品的对话，不自动恢复制作。已有发布记录按草稿身份打开，主动准备发布才调用prepare；原媒体、文件预览沙箱、删除影响预览及引用保护保持。历史方案按成片Run归属，不以当前设置补写历史。实施与回归见[LIB-01](../project/tasks/LIB-01_content-library-consistency.md)。

用户主动删除作品/指定历史版时，先展示精确影响和待删除版本；提交时核对预览版本，事务解除本次明确删除范围的保留引用并保存最小删除回执，再异步清理无其他引用的文件。不得删除用户inbox原件、其他作品共享资产或在途操作结果；有在途操作时延期物理清理，结果接收后对账。删除已接受版本必须明确指出接受选择也会移除；不擅自选择另一版替代。S6-02实现合同/保护，S6-12实现完整删除命令与UI。

## 8. 待落实的能力边界

依赖兼容与持久执行归 S6-04；外部 IMAGE/VIDEO 服务归 S6-07，任务化模型与实际多模态能力归 S6-08；编辑器版本/许可与纯制作边界归 S6-09；固定音色与字幕归 S6-10。未就绪能力必须明确不可用，不能用替身标记真实首版。

长片、四声音、跨题材及完整体验由[任务包](../project/tasks/S6_IMPLEMENTATION_PLAN.md)分批实施验收；首个可播放样片不缩减 34 项需求。执行与授权遵守任务包共同约定，实际进展和证据见[当前状态](../project/status.md)。

<a id="9-s6-14a-对话接入增量提案待评审未实现"></a>

## 9. S6-14A 对话接入合同（部署状态见项目记录）

**历史快照（A2～A4实现阶段）**：本轮起点44b3f08c；按用户当时授权完成A2～A4。原A1协议1/内存探针保持兼容，正式源码使用协议2持久桥；**代码已挂载不代表主服务已加载或主Gateway已安装插件**。本轮只运行临时Web/Gateway、临时SQLite和本地假模型。具名软件/原生/浏览器证据仅维护在[S6-14A任务卡](../project/tasks/S6-14A_conversation-integration.md)，生产身份、授权、引用和恢复仍按§3～6。

### 9.1 最少持久化与命令身份

接入记录放在原生产SQLite，迁移4只增加字段与接入记录，不新建生产队列、模型账本或全量原生转录数据库。Store.execute_command可使用宿主已经打开的事务，使原command_receipts、首次Work绑定与工具意图结果同事务提交。

| 持久记录 | 作用及边界 |
|---|---|
| conversation_segments | UI会话、固定Profile、可空Work、入口/具体目录版本/所选设置与来源、可信原生UUID、撤销时间；原生key为agent:main:easel-pipeline:segment_id |
| conversation_turns | 全局turn身份、规范请求hash、segment、用户可见消息/允许附件、派发/原生run状态、票据摘要、toolCallId意图别名与稳定命令/结果；不记录隐藏思考或原始凭证 |
| conversation_proposals | 类型、固定segment/目标/来源、Work观察版本、内容hash、状态与实际应用回执；无Work创建提案不伪造Work cursor |
| work_briefs | 每作品不可覆盖的brief版本、hash、用户原话/建议/未决项及必要来源；用于Planning与冻结依据，不依赖聊天正文存续 |
| work_conversation_links | 由明确续作入口建立的作品—UI会话关联，保留最初source_session_id；仅允许该上传会话自己的附件 |
| conversation_imports | 显式参考导入的固定请求身份、sending/succeeded/needs_review与结果，未知或失败不自动重抓 |
| 既有Work/Channel字段 | works.creation_context_json固定新作的频道语义与设置来源；channels.creative_basis_json保存独立于制作settings的定位/主题/受众 |

同turn同请求重放原job，同ID不同请求409；已有turn回放不依赖新模型派发。正式派发前持久接受，再进入原生生命周期。插件before_agent_run以可信agent/session/run原子认领预留turn；原生UUID第一次观察后固定，不能以本版本未采用的x-openclaw-session-id头代替。before_tool_call按runId+toolCallId领取绑定完整参数hash的票据，execute只能使用该关联。原生agent_end才证明运行结束；HTTP回答完成、浏览器断线或停止回答均不是该证明。

同turn同工具/参数指纹复用结果与稳定命令，不因新的toolCallId重建Work/Run。未知/在途turn不允许新turn或切换抢占；外部Work revision冲突409，不自动更新revision重发。自身已提交工具命令才可推进本turn观察版本。前端actionId按具体目标、显示版本和载荷持久保留；响应丢失沿用原ID。普通聊天的既有job/问题流不变，视频接入复用相同事件文件与GET回放，不通过再次POST来恢复。

### 9.2 具名工具、内部转发与现有 API 映射

协议2现为下列9个具名工具（8项基础工具与 `easel_pipeline`）；参数schema拒绝额外字段，宿主补齐Work/Profile/turn/command身份。没有任意URL/path、SQL、shell、Provider参数、授权、接受、发布或直接长期写工具。协议1保留A1的3工具行为，仅用于兼容探针，协议2宿主不接受协议1就绪回执。

| 工具 | 实际业务字段 | 宿主行为与权威 |
|---|---|---|
| easel_work_context | 空对象 | 当前segment所选画像/频道/导演、有限可见来源、brief、输入元数据及Work状态；冻结创作画像与当前长期保存目标分开投影 |
| easel_work_input_evidence | input_ids | 只读本Work句柄/元数据，未分析明确未分析；不把文件名或元数据当作视频观察证据 |
| easel_work_create_draft | title,input_text | 创建待确认草稿提案；当前对话经下一真人轮 `answer` 后再应用并绑定 Work，旧卡操作保留兼容；讨论本身不建 Work |
| easel_work_register_inputs | attachment_id,usage | 仅登记本 segment 当前用户来源消息中的真实附件句柄及参考/必用用途；原声、区间、Rights 不属于本原生工具参数，须沿独立具来源的确认提案处理 |
| easel_work_update_brief | entries(kind,text,source_refs) | user_requirement必须引用可见用户原话；归纳标suggestion，未决项标unresolved；活动Run拒绝修改冻结依据 |
| easel_work_request_plan | request | 产生版本化规划提案；下一真人轮确认后沿受控命令排程，不接受模型自行补写 services/grant |
| easel_work_request_revision | feedback,protected,interval | 绑定已选 Output 的修订提案；下一真人轮确认后走原 revise，扩大范围继续按既有确认规则 |
| easel_work_propose | 固定kind,values,source_refs | 只提议 channel_create/channel_defaults/director_formation/profile/director_revision；目标与来源由程序校验，应用须用户下一真人回合明确 `answer`，旧卡接口仅作兼容 |
| easel_pipeline | mode=pending/bind/draft/offer/answer，offer 带受限 action 与 values；answer 带 proposal_id/hash/user_quote/dismiss | 统一三条管线的目录读取、绑定、提案及文字确认；只有当前用户后续明确答复才能应用，UNKNOWN 新规划须单独说明重复调用风险，不得同轮自行授权或制作 |

协议2当前沿用“先提出具体提案、下一真人回合明确确认”的执行边界，主要在原生对话中通过 `easel_pipeline offer → answer` 应用；旧卡片可在独立高级路径兼容使用，但不是对话的必选提交步骤。候选正文、自动任务事件都不能冒充用户授权。无需 Work 的频道提案不创建空 Work。 answer必须显式携带严格布尔dismiss：true仅拒绝当前提案，false明确批准已展示操作；省略、null、字符串或数字均拒绝，不能把缺失决策当作批准。该校验不替代模型对真人语义的正确理解，仍保留来源、展示版本及UNKNOWN保护。

内部传输包括 `/api/chat/work-tools/entry|claim|prepare|dispatch|result|end` 入口；`result` 只凭原生可信回执读取本次 Run 的真实收口状态，不触发再次提交；由 `web/conversation_api.py` 挂载，`result` 使用 `ConversationResults` 读取状态，其他受控命令沿 `PersistentWorkToolBridge`。独立插件凭证至少24字符，只允许回环对端，使用该凭证访问其他Web路由403；浏览器Origin/Host写保护保持原规则，不全局放宽。凭证不成为模型参数或工具结果。插件只连接显式127.0.0.1 HTTP端口，禁止重定向或任意目标；可信本机安装代码不等于OS/运维隔离。

### 9.3 前端请求、依据与事件增量

| 实际入口 | 语义 |
|---|---|
| POST /api/chat/video/{session}/enter | 固定command_id与entry；核对Profile/Channel/具体Director版本/Work/Output，建立或恢复运行段与附件关联。仅浏览不调用此写入口，绑定不授权制作 |
| GET /api/chat/video/{session} | 当前segment/Work/入口、类型化提案/实际回执、本段可见讨论和turn状态；不返回原生秘密转录、隐藏思考或其他画像历史 |
| POST /api/chat/video/{session}/proposals/{id}/apply | command_id/hash/dismiss；固定目标与显示Work/catalog版本，旧卡/旧段/在途turn拒绝；已应用提案重放原回执 |
| DELETE /api/chat/video/{session} | 撤销继续工具能力、清理接入正文/附件/回答副本与待提交提案；保留最少在途核实身份和独立Work/brief/目录/成果 |
| POST /api/chat/video/{session}/reference-import | 用户显式HTTPS直链导入；固定segment、Work revision和命令；reference-only，不生成授权 |
| POST /api/chat/stream | message/attachments/sessionId/turnId/videoSegmentId；服务端仍识别已绑定视频会话，漏带mode不回普通main。workId不再短路plan/revise |
| GET /api/chat/jobs/{turn}/stream | 既有事件文件回放，不执行模型或工具；视频流含token/activity/work_card/done/error，work_card为程序投影，前端也可GET恢复 |
| POST /api/production/works/{id}/basis | 空闲且未确认Plan的本片内容/导演/设置调整；新导演试片可在同Work承接首版，已确认方案的风格变化要求修订 |
| POST /api/production/directors/{id}/analyses | 准确base Director revision、新Work输入版本和参考句柄，复用analyze_director；保留旧版本/evidence，不用revision接口伪造新分析 |
| 既有Work命令/快照/SSE | confirm/grant/resume/cancel/accept/delete 均需受控确认；对话内以已展示提案及下一真人回合 `answer` 为主，旧卡接口保留兼容；Plan/Run/Task/Artifact/Review/Acceptance/Work cursor继续作为唯一业务事实 |

候选conversation-links/briefs/conversation-context三条外部路由没有额外新增：关联统一由enter办理，brief受控工具调用同服务，恢复用GET投影。视频非流式`/api/chat`明确拒绝，不走另一个助手；普通聊天保持原功能。聊天SSE与Work事件序号分开；useWork使用独立SSE并以cursor拒绝回退快照，轮询仅补断线/遗漏，不启动后台模型。

brief保留版本/hash与来源；Planning入队保存creation_basis，Plan保留conversation_basis及原Profile/Director快照。旧第五轮没有新字段仍可读。新作频道定位/主题/受众固定在creation_context，不随后来频道默认变化。修改未确认本片设置/brief使current_plan_revision失效，旧卡不可确认；确认后风格/规格变更走修订，不回写旧Plan。

附件路径/句柄/hash/symlink检查沿用WorkService；合法新UI会话须先明确关联Work，再只能登记自己的上传附件，不能因关联而访问其他会话任意路径。模型参数不含上传路径。活动Run不自动取消，新增文件只能留待后续明确登记。Rights UNKNOWN可合法作为风格参考，不赋予重剪/原声复用授权。

### 9.4 当前单 main 运行配置与上下文合同

受控管线复用现役main，协议2、九工具、main-pipeline-v1；原生身份agent:main:easel-pipeline:<segment_id>，宿主核验真实绑定、逐次票据和插件就绪，不以HTTP200证明权限正确。普通聊天保留原工具；业务工具按受控namespace收窄。缺配置/权限或UNKNOWN不得回退CLI、换会话或重发。

同一UI更换Work/Profile须遵守固定段身份；首次从目录阶段绑定新Work的例外依原服务校验。产品上下文使用必要Profile/Director与冻结依据，不装入根研发任务。实际插件组合和指令加载须在目标部署核验，不能以静态文件分离或隔离探针冒充生产隔离。

旧双Agent/easel-video工作区配置仅见[整理前合同](../history/v2/15_IMPLEMENTATION_DESIGN.md)，不再作为安装指南。现行配置见[运行指南](../guides/runtime-setup.md)。

### 9.5 候选实施落点与最小纵向切片

> 以下为带日期的实现/验证沿革；其中“已/未部署、待验”等只属于原轮次，当前状态不在本节维护。

本节早期候选已按下表落地，详细源码/验证版本见任务卡。

| 位置 | 实际职责 |
|---|---|
| agents/plugins/easel-work | 兼容协议1，协议2工具schema、固定转发与原生生命周期；不编排生产 |
| easel/conversation*.py、video_workspace.py | SQLite运行/turn/提案/依据、来源与范围校验、同事务回执、受审查产品工作区 |
| web/conversation_api.py、web/app.py | 挂载持久桥、受限视频流、明确业务卡入口、旧main旁路阻断与聊天删除/停止分离 |
| production service/store/catalog/planning/settings | 原命令/Worker复用、brief冻结、跨会话输入、频道语义、fork设置、参考重拆和独立导演接受 |
| ChatPage/App/VideoConversation/WorkCards/ProductionPage/OutputsPage | 目录与对话入口、提案及共享业务详情、版本审阅/续作、稳定命令、独立作品SSE |

最小纵向路径已经以真实临时Web、原生OpenClaw和本地假模型执行：连续讨论→原生工具提案→卡确认→同一WorkService→稳定回执/恢复。它验证接线与权限，不评价真实模型创作质量，也未启动Worker生成新视频。

### 9.6 验证、兼容与回退

> 以下为带日期的实现/验证沿革；其中“已/未部署、待验”等只属于原轮次，当前状态不在本节维护。

A2～A4具名软件及原生检查已记录任务卡；A5已完成28项离线交互矩阵、并发/断线/完整本地媒体链；A5 当时尚未执行正式部署及真实 Web 验收；后续已实施部署、发生真实试跑但作品质量仍 FAIL，软件/隔离 Web/真实生产/Creator 接受分别记录。原A1 JSON绑定其历史源码，不因新改动改写；协议1原生复测单独记录。

迁移4在临时旧schema3兼容用例执行并验证原作品/命令回执不变，未迁移正式库。正式源码变更后需按部署计划备份和受控重载唯一服务，再核实reload_required=false，不让旧Worker处理新命令。不装正式插件、不重启服务或调用真实模型是当时 A5 测试的执行边界；后续部署另有独立授权和事实，不能用这一历史表述判断当前尚未部署。

回退停用新入口/插件，保留普通聊天、作品/目录/输入/媒体与所有原账本；未知已派发请求只核实，不通过旧短路或CLI重跑。关闭页面、停止回答或删除聊天均不取消生产，取消制作使用原cancel命令。

<a id="97-交付闭环与长期回写补充提案未实现"></a>

### 9.7 交付闭环与长期回写（已实现受控保存，发布/归因另行）

自动完成事实继续由Artifact/QC/Run/Task/Operation/event登记，不以聊天done或旧manifest“已完成”代替Creator接受。指定输出反馈用原reviews/revise与影响确认；接受用独立acceptance/accepted_output_id。接受A后生成B不自动换最终选择；库只读已明确接受版。署名/受管目录和媒体访问保护不放宽，不复制到旧目录伪装发布。

长期提议保存于同一类型化proposal，含固定segment/Work/目标、可见来源、差异、hash及回执。模型只能提议，不应用。只保存有用的1～3条；忽略/拒绝/无Profile不写、不创建全局记忆或后台学习Agent。用户主动编辑六维仍用原Profile编辑入口；学习保存仅限绑定Profile的style/preferences/memory，不能把单片规格自动变身份/经历或全局默认。

Profile提案显示target、file、before_hash、after与entries。程序持有目标文件锁比较before/after，验证仅追加卡片条目，原子替换再留SQLite回执；若文件已为同after hash，只补回执不重追加；若文件既非已知before也非after则409，不覆盖并发编辑。跨目标分别执行和留回执，不假装跨文件/SQLite原子提交。冻结创作画像和当前profile_save_target分别投影，保存后只影响新作。

频道默认提案固定频道revision，保留未修改项与其他导演关联；导演另存保留原evidence，仍需风格确认/对应版本试片/独立接受。新的参考通过真实analyze_director建新版本，旧accepted版本与Plan不改。不因长期提议自动产生付费分析、试片或语义QC。

**发布/归因是后续具名任务，当前未实现V2发布适配。** PublishPage仍用旧媒体选择，不能让聊天模型任意传内部路径或获得发布工具。后续须绑定具体work/output/digest、请求时acceptance、Profile/平台账号/真实帖子或草稿回执；成功端不重发，未知不盲推，补日志失败不重复真实发布。平台转码变化另记派生版本。旧publisher/calendar/publish-log并不提供此exactly-once保证，不能冒称已接通。

归因后续复用data-tracker/publish-log/真实指标来源，固定账号、画像、日期及output；不补造指标，不以相关性声称因果，不将报告写入共享context跨画像传播。分析可以提出长期建议，真正保存仍走本节明确卡操作。未授权的新抓取、定时任务或模型调用不会因作品完成自动发生。

<a id="98-频道导演入口依据来源与续作补充提案未实现"></a>

### 9.8 频道/导演入口、依据来源与续作

三个入口汇入同一对话：普通创作、频道选定上下文、具体已接受Director版本。目录浏览不建Work/Run；可先讨论频道/导演设置，无画像也能讨论或做独立作品，保存频道须选已有Profile。一个Profile多个频道，频道/导演多对多；默认钉准确已接受版本，新Director版本不自动升级默认。

本片明确选择优先于频道/画像默认；频道后选不暗换已明确导演。制作设置只填允许字段，Director不覆盖固定声音/字幕。跨Profile不转移原Work；活动Run不改输入或重绑工具。旧作恢复冻结依据；同Profile仅assignment改收纳，不重剪或改Plan。

频道创作依据为creative_basis(position/themes/audience)字符串，沿用catalog revision，不能写未知settings键。新作creation_context固定语义及来源；Planning任务再冻结完整profile/director/settings/brief。临时讨论要求不自动变频道长期项，保存须显示目标和差异。

fork接受明确inherit_settings集合：director_revision/voice/subtitles/duration_seconds/aspect_ratio/audio_mode；未选取频道当前默认。原未接受导演必须仍明确为trial；不复制原grants。所选原输出仅作为新作reference且Rights UNKNOWN，不成为可直接重剪或复用原声的许可；原作Plan、接受选择与文件不改。

目录/历史/代表试片投影原Work/Plan/Acceptance；未接受与已接受作品按LIB-01在内容库分区收纳，继续创作沿原作品身份。归档默认不可悄悄替换。正文“可以按这个做”只定位确认卡，不直接生产或保存长期目标。

<a id="99-创建提案目录卡与恢复整体审查补充未实现"></a>

### 9.9 创建提案、目录卡与恢复

频道：入口/对话→有来源未保存提案→一次明确保存→catalog回执→同一对话承接本期内容。没有Work也可保存，不制造空作品；失败显示失败，重复/丢响应按原命令核实，不重建频道。修改提议生成新hash使旧卡失效。

导演：参考意图→参考Work草稿确认/输入登记→明确分析提案→原analyze_director任务及真实参考证据→风格草稿→明确风格确认→同Work正式内容/首版试片→独立作品/Director接受→可选关联并设频道默认。每步使用独立稳定命令/回执，从未完成步继续；分析成功或UNKNOWN不重派。风格确认不启动生产，不接受空导演为可用风格，也不强制额外付费短片。

参考导入只允许无需登录的公开HTTPS视频直链，最多100MB；逐跳校验公网地址，固定经验证IP连接并保持TLS原hostname，无代理继承，ffprobe验证真实视频。模型没有URL下载工具。网站页面、登录媒体或无法访问来源如实提示未分析，可上传文件。UNKNOWN/失败记录不自动下载重试；本轮仅用离线下载fixture验证，真实外网源未验收。

Director接受独立检查：准确style_confirmed版本、实际Plan.director_revision_id、可见output与文件hash；完整QC passed或受限manual_review_only资格。人工资格还须技术pass、语义not_tested且无任何semantic fail/partial、成功Run和reviewable Work、明确manual_review_confirmed；只写director_accepted回执，不把QC改为PASS，也不依赖作品已经接受。设频道默认依赖该Director实际接受，必须关联并保留其他关系。

删除聊天撤销工具继续能力；正文/附件/回答副本清理，保留最少在途turn/命令映射直到核实。Work、必要brief、目录和媒体独立存续。原生内部历史不会复制回新Work/Profile段；宿主撤销访问不等于已经物理清除Gateway磁盘上的原生转录，不以此宣称完整账户数据擦除。

### 9.10 A2～A4实际落地与部署边界

> 以下为带日期的实现/验证沿革；其中“已/未部署、待验”等只属于原轮次，当前状态不在本节维护。

A2持久记录/来源/工具桥与频道语义、A3统一对话/程序卡/共享详情、A4审片/版本/独立接受/受控保存/续作均已实现。源码入口为[easel/conversation.py](../../../easel/conversation.py)、[持久工具桥](../../../easel/conversation_bridge.py)、[Web适配](../../../web/conversation_api.py)、[共享作品详情](../../../web/frontend/src/components/WorkCards.tsx)和[对话入口](../../../web/frontend/src/components/VideoConversation.tsx)。

已执行的是具名软件回归、原生隔离HTTP/Web探针及部分实际浏览器操作，证据和限制见任务卡。**A5 当时的28项离线矩阵及完整本地媒体闭环已通过；本句中“正式插件/迁移未执行”仅为 A5 历史时间点，不是当前部署状态。后续已正式部署并进行了真实 Web 试跑，质量失败及未接受状态单独保留。** 不用实现状态替代这些运行结果；具体部署字段见运行说明，不在此保存真实凭证或个人配置。

### 9.11 A5验收后的合同补正

> 以下为带日期的实现/验证沿革；其中“已/未部署、待验”等只属于原轮次，当前状态不在本节维护。

入口导航每次具名选择生成新的enter命令；服务端按同Work/依据复用原运行段。导航不创建Work/Run，避免永久复用旧导航回执导致当前段未切换。生产/保存命令仍按精确目标、版本和载荷持久去重。

创建前对话与Work创建共用merge_creation_settings，字幕按字段继承，音色与导演身份整体覆盖。Planning将固定voice/subtitles按同一Pydantic合同展开后比较，等价缺省值可通过，明确变更仍阻断。频道名称要求非空文字，非法提案保存失败时保留proposed且无catalog回执。

受限工作区装载经审查的Easel产线交互知识及来源SHA，保留“先让用户看见方案、预览和真实检查，再作明确决定”的经验；不加载旧可执行技能。A5 历史 memory-core 组合实测仅暴露8个作品工具；当前部署后受限插件精确握手为9个工具，更广泛插件/自动记忆/slash入口的安全保证仍以实际核验为准，不能推广为OS隔离。

界面显示具体导演名/版本、参考文件名和中文任务状态。已接受的当前作品版、已生效的频道默认显示完成并禁用重复提交；独立失败项仍可单独处理。普通聊天通过明确视频入口才进入作品模式，内容库分区展示未接受与已接受作品，不因有新预览换掉原接受选择。逐项运行证据见[S6-14A](../project/tasks/S6-14A_conversation-integration.md)。


### 9.12 A6对话管线入口

> 以下为带日期的实现/验证沿革；其中“已/未部署、待验”等只属于原轮次，当前状态不在本节维护。

当前对话笔入口复用管线分组，并列视频创作、创建导演、创建频道；同UI调用现有enter创建/复用可信运行段，预填引导但不发送、不建Work/Run。上下文读取失败或在途/UNKNOWN拒绝时不更新本地绑定与输入；切换成功后旧轮询响应不可覆盖新段。创建频道不携带旧频道目标，创建导演不携带旧导演，新创作不携带旧Work/输出；具体画像及选定频道/导演继承以服务端当前上下文为准。普通技能仍保留原预填行为。

三条入口接续原提案、确认卡与受限OpenClaw桥，未新增业务工具或权限。前端当前流程引导不等于用户确认，保存、分析、制作与接受仍按原合同独立进行。[交互设计§15](../history/v2/20_CONVERSATIONAL_INTERACTION.md#15-对话管线区域的统一入口用户澄清)给出流程图；[A6任务与证据](../project/tasks/S6-14A_conversation-integration.md)区分本轮菜单验证和A5历史闭环验收。


### 9.13 对话执行接入增量（已实现并部署；真实用户验收仍未通过）

> 以下为带日期的实现/验证沿革；其中“已/未部署、待验”等只属于原轮次，当前状态不在本节维护。

2026-10-19 用户确认三条既有管线通过对话选择与执行，缺频道/导演必须对话补选。具体范围、语义确认合同、轮次交接、回执及验收统一见[交互设计§18](../history/v2/20_CONVERSATIONAL_INTERACTION.md#18-既有管线的对话执行接入方案2026-10-19)。这是§9.2/9.12卡片独占提交方式的计划变更，不代表协议2已有执行权限；正式工具schema、白名单、握手及运行指令须随实现核验。沿用ConversationService/CreativeCatalog/WorkService/Worker，不另造生产控制器。以上“待评审/未改动”是 2026-10-19 提案阶段的历史状态；后续已完成代码整合、部署与真实试跑，当前以本节最终合同及当前状态页为准。

用户后续已授权实施。协议2工具集扩展为9项（新增easel_pipeline），与旧8工具运行时握手不匹配时阻断，部署须同步插件manifest/注册及Agent白名单。工具身份仍由原生生命周期绑定，内部answer可在被核验的当前turn事务中应用提案，外部卡接口仍拒绝活动轮次；不移除通用并发保护。实现与验证范围见交互设计§18.8。

**现行交付合同（2026-10-20，`fb309910`）**：PR #10/#11/#12 的代码已进入 V2 主线并部署；实际协议2为9工具、内部桥5入口。执行提案经当前真人确认后，先提交业务事务、释放锁，再由原生工具等待可信回执绑定的 Run 收口；规划/扩大修订范围后只交付新 Plan，不自动开始制作；正式制作及局部修订等待既有检查/自动修复链的真实终态。助手正文持久化并确认交付后 Web 才发 `done`；连接中断、原生超时和生产失败单独记录，不取消或重发已提交 Operation。`replan_after_unknown` 只能在核实权限与风险、展示提案并取得下一真人明确确认后执行。详见[交互设计 §18.14.1～18.16](../product/interaction.md)和[S6-14A](../project/tasks/S6-14A_conversation-integration.md)。整合版本离线生产 693 passed / 5 skipped，Node 113 passed；此前真实试片画面/时长不合要求，未由整合版真实重新验收，`REAL_PRODUCTION_PASS` 和 `CREATOR_ACCEPTED` 均不能记 PASS。

规划授权补记（2026-10-19）：旧request_plan与pipeline plan均在提案时绑定实际模型services，应用已确认提案时不可追加未展示服务；授权与排程复用同一事务，缺项/变更在排程前返回对话。仅当前permission_missing的plan允许grant携带decision_id，在明确“授权并继续”后原子保存授权及恢复；待核实外部操作仍阻断。范围与验证见[交互设计§18.10](../history/v2/20_CONVERSATIONAL_INTERACTION.md#1810-规划授权与对话中断修复2026-10-19)。

授权提案契约补记（2026-10-19）：planning的offer grant可只传purpose，由程序在提案阶段构造真实服务三字段数组并绑定当前permission_missing的plan恢复目标；工具返回完整待确认范围。显式services结构与实际能力在offer/apply均核验，不能到用户确认后才发现结构错误。旧错误提案在pending标记不可answer并给出有界修复指引，UNKNOWN不引导重试；具体证据见[交互设计§18.11](../history/v2/20_CONVERSATIONAL_INTERACTION.md#1811-授权参数契约与旧提案恢复2026-10-19)。


### 9.14 S6 当前作品的最小修复合同（2026-10-20，已部署、真实路径待验）

> 以下为带日期的实现/验证沿革；其中“已/未部署、待验”等只属于原轮次，当前状态不在本节维护。

同作品 bind 未给 work_id 时保留当前作品；显式新作仍经既有 enter，不能按标题去重，也不能靠空段变更已冻结设置。制作 offer 从当前 Plan 绑定 revision/hash，显式错误值拒绝；依配置、冻结声音与素材/剪辑/检查依赖构造并展示完整服务清单，answer 只复核，不扩张已展示权限。当前完整 Plan 单列于 pending 与结果投影；历史方案不删除。

预成片声音修订复用 plan：仅支持已确认 mixed→voice、无 BGM 或可选 SFX；无 output、无 Run owner、无在途/UNKNOWN，且原 production Run 已安全停止。取消作品需明确恢复；提案绑定原 Plan/hash、Run/revision、创作依据与受保护 Plan，以及实际规划服务。answer 在一个事务复核、将旧 Run 置既有 superseded、收口未完成任务、撤销旧授权、更新声音目标并排程新 Planning。失败全部回滚，旧 Plan/素材/Operation 回执不可改写；模型沿既有有界纠正保持观点、逐字稿、镜头和其他设置，生成未确认 V2 后必须重新确认制作。原画像快照、导演版本及对话依据随 V1 保留。有成片走 revise；UNKNOWN 仍走独立专用规则。普通 basis 不提供已确认方案例外。

搜索 API 使用与下载相同的显式 localhost HTTP 代理配置，固定 API 目标，禁环境代理继承和重定向；原下载公网 DNS/固定 IP/TLS/SSRF 规则不变。素材结果只从当前 Run 的已有事件汇总全部已知缺口，区分网络/HTTP/空候选/权益/下载/资格原因并标记候选尚未通过审查。既有 activity 展示执行阶段与整理结果，无新气泡/面板/调度节点。具体范围、命令、证据与未覆盖项见 S6-14A 本轮收口记录。


### S7 工作包实施合同（2026-10-23）

只针对新建作品。`revise.scope`为`edit`（默认）、`narration`或`boards`。narration支持含旁白的voice/mixed且无受保护原声，与preserve_audio/render_only互斥；mixed保留原BGM/音效模式、语音与交付设置，按新音轨重新编排，不将冻结整条旧音轨冒充改稿；boards与render_only互斥。两者沿既有范围确认→新规划→正式制作确认，未确认不调用新TTS/供料。narration保护交付设置、场景身份、画面与图解；原生规划以口播差量响应合并完整方案，只允许原场景的narration/narration_pauses/必要duration及口播元信息，受保护设置、visual/purpose和图解不由模型重写；回执按实际请求schema重建。visual里的旧口播锚点/字幕说明不能覆盖新版narration及实际对齐结果。boards保护设置、脚本、全部场景及图解身份/卡片事实，只允许states变化。原版及授权/UNKNOWN保护保持；新版依据生成受影响图片，不放宽旧图解顺序校验。

`Scene.narration_pauses`默认空，最多4项`{after,seconds}`：after为去首尾空白后严格递增的内部字符位置，seconds为0.05～1秒，单场总计不超过3秒。正文禁止供应商停顿标签。仅固定MiniMax speech-2.8-hd/turbo、连续旁白且无原声保护可用；不支持则明确失败，不切声音。按连续片段映射位置，编译版本minimax-pauses-1，每请求最多32处；预留时间包含停顿，实际音频过长仍停止。TTS请求保存literal_text、pauses、prosody_version及编译text；发送前重新编译严格核对。Operation和音频复用键包含实际请求（segment_id不参与声学复用）；字幕、对齐与语义正文使用literal_text，不含标签。自然表达规则natural-expression-2随作品冻结，复用原写稿调用；软件通过不证明听感。

可选独立审片服务由`EASEL_REVIEW_*`选择，使用review-api/model/structured身份、独立配置指纹和同一Operation账本；runner仅替换完整审片调用，创作上下文/写稿模型不替换。新身份须在正式服务确认中授权；无授权阻断发送，UNKNOWN不重发。未配置沿原审片；显式配置无效时运行时拒绝初始化并报配置错误，不静默退到创作服务。能力目录只证明声明/协议符合，verified_live固定false，不证明供应商实际理解。

自然入口new_work可无画像、无频道，仍须显式导演；channel_create保留画像要求。有画像作品保留频道要求，临时作品不回填默认画像或记忆。标题排除否定发布语义。既有上下文投影、回合告警归属和持久恢复机制不另造实现。

1080P编码规格1080p-h264-2为libx264/medium/CRF18/yuv420p/30fps，写入engine及RenderOutput；job与镜头缓存身份包含规格，规格变化拒绝恢复旧job。实现和部署须对照当前状态，历史效果对照见任务包§10.2。画幅仍为横竖1080P，不增加4K或强锐化。

`GET /api/production/maintenance/summary`返回操作/任务聚合、已登记资产字节及磁盘余量；耗时口径为created到updated（含等待），缺provider账单时usage_cost=null，不能作零费用。`GET /api/production/maintenance/render-cache/{job_id}`预览；POST同路径使用既有Command.payload.preview_hash明确执行。仅已完成、未接受且无在途/UNKNOWN的作品job可清理未登记引用的scenes/NNNN.mp4或json；持有execution/terminal锁和事务，执行前重验摘要。符号链接目录拒绝，成片、字幕底片、素材、project、回执、检查点和备份保留。哈希过期/锁占用/元数据缺失均拒绝，不扩大扫描、无自动回收。只在隔离测试执行删除，不触碰用户实际素材。


**审片配置投影补正（2026-10-23）**：review.available保留完整音视频配置含义；configured_mode/active_scope投影实际manual或full策略，full_av_required为full时true，blocking仅标完整检查为当前所需但不可用（或显式review配置无效），visual_video单列无声视频能力。不把manual抽帧检查写作全片语义通过。新增minimax-video-url只用于视频视觉协议；音轨要求仍仅允许已有明确支持音画的协议，错误能力标签不能放宽该保护。真实探针/配置及剩余依赖见接口调试记录，静态available不表示实际服务已普遍验证。

<!-- 旧路径章节锚点兼容；现行正文以本页内容为准。 -->
<a id="94-openclaw-运行配置与上下文合同"></a>
<a id="s5--代码复核后的可执行设计"></a>

<!-- 旧章节链接兼容；按现行正文与指向的历史来源阅读。 -->
<a id="9-s6-14a-对话接入合同协议2已部署历史-a2a5-证据保留"></a>


### 自然表达与时长策略通用修复（2026-10-24，本地离线范围）

频道提供定位和受众，导演提供讲述与视听风格，用户已确认要求决定内容边界。对话简报保留硬要求与建议的区分；规划复用原有写稿调用，先组织符合所选导演的完整思路，再落实分镜。出处与补充资料按用途进入facts/visual，不要求全部朗读。不统一聊天文体、不新增润色调用或审核。

自然定长方案的duration_seconds及场景秒数为规划估计，口播预算不将其变成必须压缩或填满的目标；固定时长仍使用原预算校验。冻结前先确定时长策略再执行对应预算处理。局部口播/图解修订继承原时长策略，不隐式改变。

素材意图的音效timing_basis区分absolute与scene：默认absolute保留已有记录语义；新自然定长普通装饰音效使用scene，沿用cue_id/scene_id，在实际剪辑场景内安排，支持原场景ID、-cutN及_N数字拆镜；同场景连续或重叠镜头合成可用时间窗口，允许环境声跨镜头，不跨其他场景空隙，草稿at不再锁死位置。供料记录保存该依据；固定时长作品仍按absolute处理。既有音效绑定检查复用此依据核对身份、角色、必需性、窗口与时长；剪辑生成在现有有限修正回调内执行同一检查，最终编译和渲染仍复核。已知音效绑定/角色错误可经原resume修正最新已返回剪辑，复用本片媒体，不重新供料或配音；UNKNOWN不得借此重发。受保护原声和绝对时间音效不自动重排，不放宽授权与素材权益。真实口播效果、部署与当前作品复验未包含在本轮离线验收中。


### 渲染文字与失败回传修复（2026-10-24，本地离线范围）

实际故障链：资料说明把中心坐标当成左边界，固定时长剪辑路径跳过已有文字布局检查，最终渲染时报越界；自动失败解释在读取上下文后触发OpenClaw回合内输入超预算（日志估计252790 token，可用236000），官方截断未减少工具结果，随后恢复请求被已结束的Easel原生绑定拒绝。未修改OpenClaw或重开已结束运行的权限。

复用现有caption_layout/check_caption_layout，将固定时长和无旁白时间表路径一并接入同次剪辑模型的格式修正；字段说明明确文字中心坐标，反馈标识具体文字层。无新增审片或审核调用。

失败/暂停/取消结果仍通过原proposal事件游标和conversation_turns去重，服务端按已记录任务直接生成状态说明并持久完成回传，不再为确定失败调用创作模型。成功方案/成片仍走现有原生解释流程。会话view增加当前活动运行的production_status，原页面轮询直接展示失败原因，即使解释为空或中断也可见；运行离开阻断状态后移除该提示，不赋予恢复或重试权限。

受测源码6084b4ca加本轮工作区改动：关联Python回归156 passed/1 skipped；前端8项通过，TypeScript/Vite构建通过。未重启服务、未恢复制作、未触发真实模型调用；构建曾写入默认静态目录，已恢复原index-Cgn6vlFA.js入口。真实Web与供应商复验NOT_TESTED。

本轮部署补充：用户随后授权部署、保留已有媒体恢复；又明确改为自行Web调试。恢复入口对已确认的文字越界渲染失败复用原剪辑回执和格式修正路径，保留失败渲染记录；此恢复路径只用已有媒体，跳过配音准备和补素材。普通本地渲染故障仍按原重试机制执行。关联离线回归166 passed / 1 skipped，前端8 passed，构建与差异检查通过。已构建并重启本机Easel，HTTP200、前端index-Dea0HdEj.js；未发送恢复制作指令，原Web失败展示与成片自动回传真实复验交用户操作，仍为NOT_TESTED。

状态展示收敛：按用户反馈，失败提示复用Easel现有对话卡片的主题变量、圆角、边框和文字层级；接口从同一份失败证据提供标题、失败原因、已完成步骤和保留说明，普通消息仍由同一数据生成，不解析中文段落推断业务状态。只调整展示，不添加审核或恢复按钮。后端13项、前端3项及构建通过；已部署index-DXplK4wk.js，实际原会话只读接口返回结构化暂停状态。静态卡片排版已查看；未代替用户恢复制作或执行Web制作验收。

#### 续作路由与对话消息位置（2026-10-24）

用户授权修复、离线测试和部署，真实制作由用户自行验证。已确认根因：render_failed没有被pending列入既有恢复选项；offer通道统一要求另轮确认，导致明确续作被误提为plan；失败卡独立放在全部消息之后，持续占据对话尾部。

复用边界：pending暴露现有resume；本轮真人明确续作且引用真实原话时，offer resume在同一事务复用原提案回执、apply、WorkService恢复和结果订阅，不新增执行器或审核。程序核对当前作品/运行/任务和未确定调用，原授权及预算继续生效；生产暂停时普通plan返回恢复入口，不生成错误规划提案。询问、否定或仅讨论不是执行意图，交由创作Agent判断；UNKNOWN与新增授权仍沿原机制。文字越界恢复只复用已有媒体的约束随编辑、渲染、检查及局部修订传递，禁止后续补料绕过本次恢复范围。

消息位置：移除底部常驻状态卡，复用任务回传的原消息身份。已记录的失败解释若中断为空，读取该结果事件恢复失败文字，无模型调用或生产写入；历史失败保持历史语义。以其后真人回合身份定位消息，已有本地历史用原话及出现次序作为展示锚点；更新和刷新不重复追加，不因新用户消息把旧失败移到最末。当前作品、素材、配音和生产断点不因展示修正而改变。

本批适用回归：Python对话、恢复、上下文、编辑/修订共239 passed；前端112 passed；构建、2990条文档路径与diff检查通过。已重启本机Easel，静态资源index-C6fopnUH.js；原会话只读接口返回恢复的失败消息及其后真人回合锚点。部署前无活动运行/对话回合；部署后该作品仍为原暂停版本，42项产物、10次业务调用不变。未发送续作指令、未应用或删除现存提案，未调用真实模型或重新生成媒体；真实续作及成片回传验收由用户执行，NOT_TESTED。

#### 明确重新规划与续作的边界修正（2026-10-24）

用户授权修正上一批过宽的plan拦截、测试后部署，制作仍由用户验证。对话Agent按本轮语义区分resume与plan，不使用关键词识别。明确改变已有方案时，复用offer plan，使用intent=replan、具体request和本轮真实user_quote；业务层以原方案版本、运行版本及创作依据绑定目标。普通plan遗漏意图时提示两个合法路径，不把所有暂停状态一律解释为续作。未确认方案也可明确要求换一版。

在原运行已安全停止且无在途/UNKNOWN调用时，复用_plan和现有Worker：将旧运行标为superseded，保留旧方案、产物和回执，撤销旧制作授权，沿用有效规划授权，新建planning运行。已有相同规划模型授权时同一真人回合直接应用提案，无重复确认；缺少授权时仍通过原提案展示真实服务并确认。新方案完成仍停在awaiting_confirmation，不自动制作。正在运行、已取消或未知结果各保留既有处理边界，不以重新规划绕过。

离线证据：对话、规划及既有声音修订关联回归232 passed；补充未确认方案边界后，定向39 passed（与前者有重叠，不相加）。覆盖同运行续作、明确改结构重新规划、原媒体/旧方案保留、无新制作自动执行、规划授权缺失，以及活动运行/UNKNOWN不变。文档与差异检查通过；当前作品仍原暂停版本，42项产物、10次调用，未实施业务操作。真实模型意图选择与制作验收NOT_TESTED，交用户验证。

已部署本批后端与创作对话策略并重启本机Easel；原会话只读接口正常返回，作品仍为needs_decision。前端本批未改，沿用上一批已部署资源。未升级或修改OpenClaw，未发送恢复/重新规划指令。

#### 修订观察成片与当前失败提示（2026-10-24）

用户授权本轮修复、离线测试和部署，真实续作由用户验证。根因：修订首轮已展示成片抽帧，却未将具体修订目标加入inspect_media的句柄和路径范围，已成功返回的模型查看请求因此被本地拒绝；失败汇总又读取了已取消渲染尝试的旧error_json，并把quality任务succeeded误当检查通过。

复用既有机制：修订上下文标明review_output及成片时间，原观察工具仅额外准入该次指定版本，仍复用artifact_file的身份/文件校验和原抽帧预算，不准入其他作品/版本、不将成片作为替换素材。显式resume可将已成功MODEL回执中的只读inspect_media请求作为原有runner的恢复来源，原请求/回执不改、不重发原作者调用，沿同一有界工具循环继续；无新审核。pending补齐此修订工具失败的既有resume入口。

提示按当前运行内每种步骤的最新尝试汇总，只输出仍处于失败/待处理状态的错误；已取消或已被后续成功替代的错误保留审计，不再冒充当前阻断。quality从“已完成”步骤中分离，按真实result_json展示技术、抽帧或内容结果；任务执行结束没有结果时只写待核实，not_tested不写通过。既有失败回传用原事件快照投影最新措辞，保持原消息身份和位置，不按当前运行重写历史事实、不修改历史数据库消息。revise显示为局部修订，已恢复过的作品不再显示“尚未恢复制作”。

离线证据：修订、对话回传、原片渲染、素材边界等关联214 passed；补齐修订恢复入口后该组定向22 passed（重叠不相加）；前端消息排序/去重7 passed。真实FFmpeg夹具验证指定成片抽帧、跨作品请求拒绝，以及已收到工具调用的恢复：原MODEL回执不变、作者请求只执行一次、已有媒体字节不变。另覆盖已取消旧渲染错误不展示、检查发现问题不写通过、未知检查结果不补推通过、旧持久消息按原事件纠正展示。真实生产续作及修订后成片回传NOT_TESTED。

已重启本机Easel加载本批后端修复，原会话只读接口和对应失败消息均显示纠正后的当前阻断。部署前无活动运行/回合；部署后对本作品works/runs/tasks/operations/artifacts完整行快照比对一致，45项产物与13次调用不变。未恢复修订、未重新渲染、未触发真实模型或素材/配音生成。前端本批未改，不重复构建。

续作指引补充：用户指出失败通知缺少下一步。提示复用pending同一份编辑/修订恢复入口判定，在可恢复且无UNKNOWN的暂停状态末尾展示“可在本对话回复继续制作，将核对恢复条件并从原断点继续，保留已有素材和配音”。只补对话指引，不新增按钮、重复确认或自动派发；已取消任务、未知结果和无对应恢复入口不展示盲目重试指引。关联对话/恢复109项测试通过。

### 旧渲染替代后的收尾与成片回传（2026-10-24）

- Worker 收尾复用任务依赖与 `edit_recovery_requested` 记录：只有同一运行内已取消的旧 render、成功的原 edit、恢复后新建且成功的替代 render 三者对应，才将旧尝试视为退役。取消本身不等于成功；真实未完成依赖、其他失败或未确定 Operation 仍阻断。旧失败记录保持不变。
- 已受错误 `dependency_blocked` 阻断的运行可通过 `Worker.reconcile_completed_run` 做幂等收尾核对；只接受当前无执行所有者、未取消、版本匹配且所有有效任务完成的运行，追加原 `run_completed` 事件。不启动任务、不重渲染、不改变审片或接受结果。
- 成功渲染的交付按最后一个成功 render 的 `output_id` 精确选择可展示成片，复用原结果订阅、持久回合和本地交付通道回传视频及实际检查范围，不为既定结果另调模型。方案等仍走原对话机制；检查未验证不改为通过，保留既有后续动作引导，不代替 Creator 接受。


**PUB-01指定完成版本接受补正（2026-10-24）**：作品接受针对具体output，不依赖后来规划导致的Work状态；manual路径保留技术pass、manual_review_only、无已知semantic fail/partial、完整人工确认与文件身份。所属Run成功，或Run已superseded且已有run_completed早于run_superseded的持久事件，均可证明该版完成；被替代但未成功完成的Run不具备资格。此规则不将后续规划取消/恢复，不伪造QC PASS。数据库schema6同步接受约束；Director独立接受合同未改变。


**PUB-01发布恢复与回执补正（2026-10-24）**：未确定的历史投稿只可查询；官方后台显式核实不存在后，resolve-absent在原发布锁内重验原账号、完整且未变的列表、版本/确认摘要、无远端ID，再将同一草稿恢复并使旧确认失效。不得据空列表或退出非零自动重传。有远端ID只核实该稿件，列表延迟不显示成“没有上传”。原biliup上传器支持可选部署线路覆盖，证书校验保留；执行阶段/代码持久化与平台审核/公开状态分开。原生文件发布和具体成片发布共用线路覆盖，无新增审核。

### PUB-01 投稿封面增量（2026-10-24）

具体发布草稿的content可选cover={digest,width,height}或null。封面候选通过publications/{id}/covers（素材路径或成片时点）及covers/upload（multipart）建立，GET covers/{digest}预览；准备候选不选择、不投稿，原save才绑定。复用已接受版本校验、本地观察抽帧和原CLI --cover。封面进入已有最终确认摘要，发送前复制校验；已提交记录禁止改图，不改旧确认摘要。首批B站封面增量未引入数据库迁移、制作任务或额外审核；多平台schema扩展见下。验证/授权边界见[PUB-01](../project/tasks/PUB-01_acceptance-publication.md)。


### 原发布中心的成片与文件来源衔接（2026-10-24）

原PublishPage保留平台多选、逐平台文案、预览、账号及结果卡。媒体网格合并公共文件和既有已接受成片投影；不打开生产目录。通用对话/内容库发布入口仅导航到具体work/output的平台选择页；查看已有草稿仍走原publication深链，不prepare或重新提交。未接受新版不代替接受版。

Publications.prepare及Web Source新增可选platform，默认bilibili兼容原调用；本批成片接入bilibili/douyin/xiaohongshu/kuaishou/weixin-channels，知乎/公众号保留原图文路径。现有B站适配器、封面、账号、snapshot/readback、恢复入口保留；其他平台由NativeAdapter薄接线调用原命令构造及发布脚本。草稿/尝试继续存原表，schema 7仅扩展平台约束并保留旧数据字段与身份。去重包含平台/账号/输出，旧文件和成片入口共享平台执行锁；原异步短信在锁内初始化，不能覆盖另一正在执行任务的状态/验证码。

普通文件PublishRequest.media保持原相对路径，可选cover为受控图片引用。新增本地/api/publish/covers来源/上传/预览接口，沿原路径权限并拒绝私有路径及符号链接；共用encode_cover，文件来源不建立Work。原公众号默认首图封面仍可用；显式封面不丢弃正文图片顺序。封面在本地草稿自动保存；成片封面仍经原revision/save绑定，未保存不能进入最终确认。共用图按用户一次操作赋给目标，之后独立编辑保存；已发记录不参与应用。

封面处理保持原比例，无新图片生成/复杂裁剪器。各原浏览器发布器新增显式封面上传步骤：入口/控件不存在时停止，不回退推荐图；无显式图保留原默认。视频号只允许提交前恢复frame，按发表后结果不明不得换frame再提交。真实平台控件/尺寸要求仍需具名验证，软件通过不承诺平台最终封面效果。

非B站无独立读回能力时snapshot记null而非伪造空列表，自动核实能力关闭；现有脚本的明确读回证据复用，未核实返回UNKNOWN并沿原记录查看，不能自动重发。普通文件原接口及状态语义保持兼容，不自动迁入生产发布表。实际证据及未测范围见[PUB-01本轮记录](../project/tasks/runs/2026-10-24-pub-multiplatform-web-01.md)。


### 2026-10-24 局部修订差量与转场编译

RevisionProposal复用原提案和恢复入口，允许changes按已登记镜头ID替换局部镜头（含原ID-cutN拆镜）、按字幕ID替换样式；未列项及独立AudioClip继承所选原工程。完整edit仍用于旧回执与声音修订，两种形式互斥；合并后执行原完整工程校验并持久化，不新增编辑器、审核或数据库迁移。

修订复用首轮compensate_edit_overlap和align_editor_frames，只有已知转场重复扣除可确定补偿，不任意拉长尾部。取源边界按编译后的时长校验。独立声音完整保留，镜头原声比较与FFmpeg一致的素材/取源/时长/增益/实际位置，视觉字段不冒充声音变化。在原有限修正轮次中收集可独立判断的当前错误；终止保留具体原因，仍使用invalid_model_output及原恢复入口，不混入历史失败。


### 2026-10-24 纯视觉修订仅输出局部变更

原生视觉修复或preserve_audio=true的修订，新MODEL请求使用只含changes的视觉提案合同，不向模型提供完整edit输出分支。所选原工程仍为输入依据；镜头、字幕按ID局部替换，未改部分和独立音轨由程序继承。统一归一为原RevisionProposal后继续既有校验、持久化、渲染与恢复，不新增修订运行。允许改声音的既有分支及旧完整回执读取保留。

模型合同title仍为RevisionProposal，恢复沿原回执身份/UNKNOWN校验和原任务；恢复的新请求采用局部合同，旧完整回答或坏JSON进入原有限修正回合，不重新发送历史调用。JSON解析失败回传行/列/解析原因，字段错误回传不含输入值的具体路径；仍用invalid_model_output，既有对话提示和恢复入口不变，不回显原始模型正文或凭证，不猜修JSON。


### 2026-10-24 BGM候选用途补正

Wikimedia音乐检索和有限回退均保留music/instrumental用途；按文件自身标题及分类识别music/speech/unclassified，不能用检索通道audio_roles或介绍中提及音乐作为实际配乐证据。明确导赏/访谈/讲话及无音乐内容声明的Commons候选不进入BGM供料，SFX来源与已有Rights/文件摘要约束保持。仅这是元数据内容类型依据，不声称已试听、无歌词或听感通过。

同一用途判断复用于库存候选和既有AudioClip绑定检查，旧库错误music标签不能继续冒充配乐，也不删除原文件。未选候选的内容不适配不能阻断整个工程；实际选用才在原有限剪辑修正回合提示具体候选原因，改选本批合格音乐。素材身份、Rights、引用和UNKNOWN仍按既有规则检查。无合适候选沿原音乐缺口/供料回退，不改纯旁白、不新建审核步骤或自动换当前片音轨。


**PUB-01 Creator审阅优先及只读重发（2026-10-24，用户明确调整）**：本条取代前述“作品人工接受必须manual_review_only且没有任何semantic fail/partial”的限制；Director独立试片接受保持原合同。技术检查通过且制作成功完成（含有完成先于supersede事件证明的历史Run）、文件身份不变的具体成片，Creator完整审阅画面、声音、字幕、同步并明确全部通过时，可用manual_review_confirmed=true登记explicit_manual_review接受。自动抽帧或内容意见保留为原始QC，不冒充自动PASS、不强制重制或清除needs_fix；事件留存artifact_digest和reviewed_check_ids，发布准备校验同一人工接受及当前文件。没有完整人工确认仍拒绝，缺失/篡改文件、未完成运行及技术检查失败仍不能伪报成功；不推定Rights或发布授权。schema8只替换接受约束，保留历史业务数据。

`easel_pipeline`mode=preview是原对话的只读成片查看：values仅允许output_id/output_revision，均缺省时返回本Work最新可见输出；不存在或跨作品版本拒绝，返回preview_output.playback_url和preview_text。此动作不创建提案/Run/模型调用/媒体制作，无需用户确认；宿主沿原持久消息投影回显播放器，即使模型答复中断也可恢复。pending摘要提供真实播放地址及所选版本最新检查findings，完整观察仍通过detail=full读取；旧版本问题不得解释成新版检查结论。


### CRE-01 主线多轮对话投影补充（2026-10-25）

受控原生对话只公开pipeline draft/offer plan这一组草稿/规划入口；内部建稿与费用授权、方案制作确认分别处理，不以模糊认可执行制作。原生工具集合、Gateway准入与配置生成一致。

结果投影保留唯一完整当前Plan及任务身份/状态/结果/错误/UNKNOWN，不重复执行输入payload；原规范记录与请求身份不变。视觉抽样visual_status和完整语义status分列，不能彼此替代。仅plan失败不声称已进入媒体制作。当前草稿失败仅投影有界审阅发现，审阅意见不升级为用户事实或需求。

ContextPreparation既有官方压缩允许在上一条已知原生结束的空length回复后，为下一条新消息做一次受控准备；须同会话/模型、无正文/工具输出，压缩未知不重发。此为有证据的恢复触发，不是长度根因断言，不重发旧消息、UNKNOWN或制作，也不承诺实时预估首次输入暴增。真实证据与限制见[CRE-01多轮调试](../project/tasks/runs/2026-10-25-web-e2e-02.md)。


当前草稿审阅视图为current-draft-3：当前candidate的facts/constraints与原参考历史分开，MiniMax声音适配器固定wire参数以同源合同投影，不成为Plan可编辑参数；图解源PNG尺寸/比例、字幕坐标空间及固定页脚能力由实际文件和渲染器测量/派生。审阅操作namespace随视图版本变化，旧成功请求/回执不改写。恢复先验证同Task原生来源；只对原回执应用与保存时相同的固定声线参数投影，保存稿自身不被规范化以掩盖篡改。视图变化可以复核既有草稿，但不重置已用纠正次数。明确改稿时，失效的当前指针不等于无历史方案；已有Plan的入口须显式replan，并绑定本Work当前或最新保留Plan与安全停止Run。


创作原话交接：新plan/revise提案在既有request/feedback中分别保存服务器从已验证source_refs读取的origin=user原文与agent_request派生整理；宿主事件不能成为真人源，确认/服务授权本身不变。新方案conversation_basis.creative_request冻结本任务最新本期补充，所有后续生产/审阅上下文优先本Task.request，否则读取所选已确认Plan的creative_request；口播/图解差量和受保护声音模式新版本保留原画像/频道/导演身份，同时更新本期补充。旧Plan及其哈希、已发送请求/回执不回填或改写，真实新依据改变新Plan/hash。仅当完整补充已在brief时，模型视图去掉Plan中的重复副本，内部冻结记录始终保留；缺源旧任务不因读取自动新增字段。
