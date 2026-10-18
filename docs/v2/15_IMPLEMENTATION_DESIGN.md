# S5 · 代码复核后的可执行设计

状态：**Coding 合同；实施与运行结果见[当前状态](04_CURRENT_STATE.md)。** 本文把已确认需求/职责落实为实施要求；技术依据见[选型建议](14_TECHNOLOGY_SELECTION.md)，执行入口见[实施任务包](tasks/S6_IMPLEMENTATION_PLAN.md)。文件、端点、表和命令描述合同目标，是否实现及覆盖范围以对应源码、任务卡和运行证据为准。

## 1. 复核结论与实施约束

业务基线 `easel-v2-rebuild@8eeafb6b9bf62b26e2077057cbebe45721f5d464`；本次复核起点 `codex/s5-architecture@d25b8f8395c907180738a5795042c3fe86e6de0b`，两者 easel/web/skills/tests 无业务差异。V1 只读 `57c8e2ade21af9fb6abccdab3f7ba8e50132314f`。

- 现有 `web/app.py` 已有本机写入保护、画像/附件/outputs/聊天 SSE，应保留这些边界；V2 用独立 router 接入，不继续把全部新业务堆入大文件。
- 作品记录是业务权威；框架检查点、素材库内部记录不拥有第二套确认/额度。网络和数据库不能一笔事务提交，未知结果必须独立处理。
- 执行者所有权、工作发现、外部操作幂等、版本和事务事件属于 Easel；不能宣称引入图框架即可获得生产可靠性。
- 模型主链推荐程序控制的任务 API 和工具分发，无任意 shell、文件浏览或直接媒体凭证。既有通用 Harness 保留给已有聊天；只有证明满足同样限制的接入才可参与 V2 收费制作，不默认用完整聊天会话当创作执行状态。
- 编辑器已在 S6-09 落实为本地 FFmpeg 受限时间线，版本、许可、真实能力与未覆盖项见 [ADR-S6-009](decisions/ADR-S6-009-local-editor.md)及[选型依据 §5](14_TECHNOLOGY_SELECTION.md#5-编辑渲染本地-ffmpeg-与可编辑工程)。不整体迁入 V1 native_source/service，不把 Hypit 后续接入作为当前主线前置。缺失效果明确返回能力缺口，不得擅自改为效果降级的幻灯片交付。

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

### 5.3 素材与渲染

M01/02把LibraryVisibility（本机拥有者/画像可见范围）与UseContext（当前work_id和用途）分开，不能用work_id把所有库资产锁为单作品。明确可复用的同画像资产可跨作品复用，current_creation_only仍绑定源作品；无画像输入默认仅本作品，后续归类不自动扩大权限。M03/04检索/获取，M05通过OperationService准入观察。不迁V1用户库，不把旧rights结果无条件用于新用途；署名/版权证据进入最终依赖。V1测试适配路径/fixtures并保留负例意图，不复制PASS数字。

S6-07分别实现IMAGE和VIDEO的适配与能力声明，S6-10实现VOICE。未配置真实服务可先做离线协议测试，但缺失模态保持capability_unavailable/NOT_TESTED；一个生图adapter通过不表示生视频已接通。S6-09已完成本地 FFmpeg 首个编辑器决定及真实合成媒体证据，范围见 [ADR-S6-009](decisions/ADR-S6-009-local-editor.md)；S6-14继续验收完整生产能力，不暗含用样片代替未实现功能。

EditProject 保存编辑器类型/版本、可编辑工程、稳定scene_id、实际媒体依赖、音色与字幕生效值。当前 `ffmpeg-timeline-v1` 是该后端自己的受限时间线，支持实际视频剪辑/溶解、图片显式运动、独立原声/配音/音乐、固定字幕；不是要求其他引擎服从的通用视觉DSL。项目/manifest/结果hash与无字幕合成底片保留供修订和真实预览。未来更换引擎须按实际能力适配，不能跨引擎偷偷丢风格特征。

原声必用区间与生成旁白分开轨道/依赖。固定voice provider/model/voice_id及相关可用参数，缺失不静默换。字幕对实际音轨对齐并结合实际画面预览；字号是对应输出分辨率的可调整参数。当前 assemble.py 会保留显式镜头时长、缺省时借旁白推导；其默认静音/补帧及缺字幕回退需在适配时显式处理，不能照搬为产品限制。

## 6. 质量、局部修订与用户可观察性

技术检查输出可解码、音视频轨、时长/画幅、素材引用、字幕时间/范围及声音线索；语义检查基于真实视听证据核对事实、观点、风格、节奏。自动检测黑场/静音仅是线索，允许有意留白，不能为PASS删除创作。

质量记录绑定精确artifact hash与检查规则/模型版本。待修候选不能成为reviewable；新输出不能沿用旧输出PASS。机器合格和用户接受分开。审美改进建议不自动变无限阻断；缺必用内容、错误事实、不可播放等属于阻断。

RevisionPlanner输出ChangeSet：base_output、affected_scene_ids、changed_audio/text/settings、expected_new_image/video_calls、scope_expansion、new_permissions、reusable_artifacts。用户清楚授权的局部低影响修改无需二次审批；扩大范围/新增生成说明随修改确认，额度不够再追加。active run期间的新修改先形成请求，不改写正在消费的P1；确需重定向则停止新派发并保留在途结果，创建新修订/run后重算依赖。

进度概览持续显示阶段/具体动作、并行任务、成果预览、消耗/待核实、阻塞及下一步；展开输入/输出和面向用户的选择摘要，不暴露模型内部思维或凭证。事件至少包括 command_accepted、task_started、artifact_registered、operation_waiting、decision_required、revision_created、quality_result、run_completed/cancelled。模型token流不是业务事件真相；长期无更新显示最后时间/状态待核实，不模拟百分比。

## 7. UI、默认与长期资产

沿用 ProfilePage/ChatPage/OutputsPage；新增频道/导演配置与作品页由现有App路由连接。必须可无画像无频道创建。频道表示系列，默认导演是已接受的版本；跨频道同风格不复制经历。

音色/字幕按本片→频道→画像解析并在方案确认时固定，后续修改默认只影响新方案。保存到长期默认须用户明确指定作用域，不能因为本片改字号就修改频道。正式首版兼试片时同时展示两个独立接受选项，不从“接受视频”推导“保存导演”。

根据画像/频道/本次风格推荐少量可用声音，支持同文试听及服务支持的语速/情绪参数。固定音色不可用时保留原设置，说明原因并列出替代试听及收费条件；用户明确选择后建立新本片设置，不静默更换或修改长期默认。导演归档后不再用于新作默认推荐；失效默认提示选择或明确取消，已确认作品仍固定原版本。

内容库展示作品选定输出并可比较历史版，保留已有文件浏览；不将旧ready/published标签当接受状态。新作品基于旧作品时引用允许素材，但新建方案与授权。画像或频道归档保留历史引用，不让同名新画像静默占用旧身份；具体重命名/删除通过引用检查或提示解除关联，已确认快照不回写修改。

用户主动删除作品/指定历史版时，先展示精确影响和待删除版本；提交时核对预览版本，事务解除本次明确删除范围的保留引用并保存最小删除回执，再异步清理无其他引用的文件。不得删除用户inbox原件、其他作品共享资产或在途操作结果；有在途操作时延期物理清理，结果接收后对账。删除已接受版本必须明确指出接受选择也会移除；不擅自选择另一版替代。S6-02实现合同/保护，S6-12实现完整删除命令与UI。

## 8. 待落实的能力边界

依赖兼容与持久执行归 S6-04；外部 IMAGE/VIDEO 服务归 S6-07，任务化模型与实际多模态能力归 S6-08；编辑器版本/许可与纯制作边界归 S6-09；固定音色与字幕归 S6-10。未就绪能力必须明确不可用，不能用替身标记真实首版。

长片、四声音、跨题材及完整体验由[任务包](tasks/S6_IMPLEMENTATION_PLAN.md)分批实施验收；首个可播放样片不缩减 34 项需求。执行与授权遵守任务包共同约定，实际进展和证据见[当前状态](04_CURRENT_STATE.md)。

<a id="9-s6-14a-对话接入增量提案待评审未实现"></a>

## 9. S6-14A 对话接入合同（A2～A4已实现，A5离线验收通过，正式部署待授权）

本轮起点44b3f08c；按用户新授权完成A2～A4。原A1协议1/内存探针保持兼容，正式源码使用协议2持久桥；**代码已挂载不代表主服务已加载或主Gateway已安装插件**。本轮只运行临时Web/Gateway、临时SQLite和本地假模型。具名软件/原生/浏览器证据仅维护在[S6-14A任务卡](tasks/S6-14A_conversation-integration.md)，生产身份、授权、引用和恢复仍按§3～6。

### 9.1 最少持久化与命令身份

接入记录放在原生产SQLite，迁移4只增加字段与接入记录，不新建生产队列、模型账本或全量原生转录数据库。Store.execute_command可使用宿主已经打开的事务，使原command_receipts、首次Work绑定与工具意图结果同事务提交。

| 持久记录 | 作用及边界 |
|---|---|
| conversation_segments | UI会话、固定Profile、可空Work、入口/具体目录版本/所选设置与来源、可信原生UUID、撤销时间；原生key为agent:easel-video:segment_id |
| conversation_turns | 全局turn身份、规范请求hash、segment、用户可见消息/允许附件、派发/原生run状态、票据摘要、toolCallId意图别名与稳定命令/结果；不记录隐藏思考或原始凭证 |
| conversation_proposals | 类型、固定segment/目标/来源、Work观察版本、内容hash、状态与实际应用回执；无Work创建提案不伪造Work cursor |
| work_briefs | 每作品不可覆盖的brief版本、hash、用户原话/建议/未决项及必要来源；用于Planning与冻结依据，不依赖聊天正文存续 |
| work_conversation_links | 由明确续作入口建立的作品—UI会话关联，保留最初source_session_id；仅允许该上传会话自己的附件 |
| conversation_imports | 显式参考导入的固定请求身份、sending/succeeded/needs_review与结果，未知或失败不自动重抓 |
| 既有Work/Channel字段 | works.creation_context_json固定新作的频道语义与设置来源；channels.creative_basis_json保存独立于制作settings的定位/主题/受众 |

同turn同请求重放原job，同ID不同请求409；已有turn回放不依赖新模型派发。正式派发前持久接受，再进入原生生命周期。插件before_agent_run以可信agent/session/run原子认领预留turn；原生UUID第一次观察后固定，不能以本版本未采用的x-openclaw-session-id头代替。before_tool_call按runId+toolCallId领取绑定完整参数hash的票据，execute只能使用该关联。原生agent_end才证明运行结束；HTTP回答完成、浏览器断线或停止回答均不是该证明。

同turn同工具/参数指纹复用结果与稳定命令，不因新的toolCallId重建Work/Run。未知/在途turn不允许新turn或切换抢占；外部Work revision冲突409，不自动更新revision重发。自身已提交工具命令才可推进本turn观察版本。前端actionId按具体目标、显示版本和载荷持久保留；响应丢失沿用原ID。普通聊天的既有job/问题流不变，视频接入复用相同事件文件与GET回放，不通过再次POST来恢复。

### 9.2 具名工具、内部转发与现有 API 映射

协议2为下列8个具名工具；参数schema拒绝额外字段，宿主补齐Work/Profile/turn/command身份。没有任意URL/path、SQL、shell、Provider参数、授权、接受、发布或直接长期写工具。协议1保留A1的3工具行为，仅用于兼容探针，协议2宿主不接受协议1就绪回执。

| 工具 | 实际业务字段 | 宿主行为与权威 |
|---|---|---|
| easel_work_context | 空对象 | 当前segment所选画像/频道/导演、有限可见来源、brief、输入元数据及Work状态；冻结创作画像与当前长期保存目标分开投影 |
| easel_work_input_evidence | input_ids | 只读本Work句柄/元数据，未分析明确未分析；不把文件名或元数据当作视频观察证据 |
| easel_work_create_draft | title,input_text | 创建待确认草稿提案；卡确认后调用原create并同事务首次绑定segment，不因讨论自动建Work |
| easel_work_register_inputs | attachment_id,usage,original_audio,rights | 只能登记本segment来源消息中的真实上传句柄；模型不能设原声true或声明使用权。原声/区间/Rights由明确UI素材操作输入 |
| easel_work_update_brief | entries(kind,text,source_refs) | user_requirement必须引用可见用户原话；归纳标suggestion，未决项标unresolved；活动Run拒绝修改冻结依据 |
| easel_work_request_plan | request | 产生版本化规划提案；用户确认后调用原plan，不接受模型services/grant |
| easel_work_request_revision | feedback,protected,interval | 绑定入口已选output生成提案，卡确认后调用原revise；保护项/区间进入该指定版本反馈 |
| easel_work_propose | 固定kind,values,source_refs | 只提议channel_create/channel_defaults/director_formation/profile/director_revision；目标与来源仍由程序校验，应用须明确卡操作 |

协议2中create/plan/revision先提案，是把首期“正文只讨论、卡片提交业务”的既定交互落实到执行边界；候选正文不被解析为授权。无需Work的频道提案不调用create。

内部传输仍为`/api/chat/work-tools/claim|prepare|dispatch|end`四个固定入口，由web/conversation_api.py挂载PersistentWorkToolBridge。独立插件凭证至少24字符，只允许回环对端，使用该凭证访问其他Web路由403；浏览器Origin/Host写保护保持原规则，不全局放宽。凭证不成为模型参数或工具结果。插件只连接显式127.0.0.1 HTTP端口，禁止重定向或任意目标；可信本机安装代码不等于OS/运维隔离。

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
| 既有Work命令/快照/SSE | confirm/grant/resume/cancel/accept/delete仍是明确卡操作；Plan/Run/Task/Artifact/Review/Acceptance/Work cursor继续作为唯一业务事实 |

候选conversation-links/briefs/conversation-context三条外部路由没有额外新增：关联统一由enter办理，brief受控工具调用同服务，恢复用GET投影。视频非流式`/api/chat`明确拒绝，不走另一个助手；普通聊天保持原功能。聊天SSE与Work事件序号分开；useWork使用独立SSE并以cursor拒绝回退快照，轮询仅补断线/遗漏，不启动后台模型。

brief保留版本/hash与来源；Planning入队保存creation_basis，Plan保留conversation_basis及原Profile/Director快照。旧第五轮没有新字段仍可读。新作频道定位/主题/受众固定在creation_context，不随后来频道默认变化。修改未确认本片设置/brief使current_plan_revision失效，旧卡不可确认；确认后风格/规格变更走修订，不回写旧Plan。

附件路径/句柄/hash/symlink检查沿用WorkService；合法新UI会话须先明确关联Work，再只能登记自己的上传附件，不能因关联而访问其他会话任意路径。模型参数不含上传路径。活动Run不自动取消，新增文件只能留待后续明确登记。Rights UNKNOWN可合法作为风格参考，不赋予重剪/原声复用授权。

### 9.4 OpenClaw 运行配置与上下文合同

同一Gateway中的内部easel-video是同一Easel助手的受限执行配置，不是新产品人格或另一个Director Agent。prepare_video_workspace.py从权威SOUL选择介绍/沟通片段，装配明确的视频产品规则与来源hash；不运行全量sync、不装入根开发AGENTS、旧生产脚本执行规则、全目录画像或全局MEMORY。创作知识与当前Profile/Director经宿主最小投影提供；媒体分析和生产仍交原任务。

运行段key=`agent:easel-video:<segment_id>`，HTTP目标=`openclaw/easel-video`。同一UI更换Work/Profile必须另开原生段，旧工具不能借新段继续。首次从同画像目录提案阶段绑定新Work可保留该段，但先等待原生end；已有Work段不改绑别的Work。恢复旧Work只用其匹配段/允许依据；没有合法旧段则新段加最小可见依据，不复制main内部历史。

宿主派发前GET受Gateway认证的`/plugins/easel-work/status`，要求protocol=2、agent=easel-video与准确8工具；/health=200不代表插件就绪。权限/绑定/配置失败关闭，初始HTTP错误直接显示；UNKNOWN保留核实，不自动切CLI或main重发。首期澄清直接在对话提问跨轮等待，不注册通用ask_user/管理工具。普通聊天QuestionCards保持原链，不把澄清回答当作制作授权。

配置生成器只输出新工作区及待合并patch，不安装或覆盖真实配置。合并时必须保留main、模型与原plugins allow/load成员；实际既有插件、自动记忆、slash/启动上下文的组合权限仍须在A5部署环境实测，不能用隔离无其他插件的结果冒充正式权限验收。测试中实际模型工具清单为8个，exec/read/会话委派/直接媒体攻击均被拦截；不宣称获得OS或凭证物理隔离。部署配置见[运行说明](16_RUNTIME_SETUP.md)。

### 9.5 候选实施落点与最小纵向切片

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

A2～A4具名软件及原生检查已记录任务卡；A5已完成28项离线交互矩阵、并发/断线/完整本地媒体链；正式部署和随后获准的真实Web验收仍未执行，软件/隔离Web/真实生产/Creator接受分别记录。原A1 JSON绑定其历史源码，不因新改动改写；协议1原生复测单独记录。

迁移4在临时旧schema3兼容用例执行并验证原作品/命令回执不变，未迁移正式库。正式源码变更后需按部署计划备份和受控重载唯一服务，再核实reload_required=false，不让旧Worker处理新命令。不装真实插件、不重启服务或调用真实模型是本轮执行边界，不能省略后续验收。

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

目录/历史/代表试片投影原Work/Plan/Acceptance；未接受作品在作品列表继续，已接受进入内容库。归档默认不可悄悄替换。正文“可以按这个做”只定位确认卡，不直接生产或保存长期目标。

<a id="99-创建提案目录卡与恢复整体审查补充未实现"></a>

### 9.9 创建提案、目录卡与恢复

频道：入口/对话→有来源未保存提案→一次明确保存→catalog回执→同一对话承接本期内容。没有Work也可保存，不制造空作品；失败显示失败，重复/丢响应按原命令核实，不重建频道。修改提议生成新hash使旧卡失效。

导演：参考意图→参考Work草稿确认/输入登记→明确分析提案→原analyze_director任务及真实参考证据→风格草稿→明确风格确认→同Work正式内容/首版试片→独立作品/Director接受→可选关联并设频道默认。每步使用独立稳定命令/回执，从未完成步继续；分析成功或UNKNOWN不重派。风格确认不启动生产，不接受空导演为可用风格，也不强制额外付费短片。

参考导入只允许无需登录的公开HTTPS视频直链，最多100MB；逐跳校验公网地址，固定经验证IP连接并保持TLS原hostname，无代理继承，ffprobe验证真实视频。模型没有URL下载工具。网站页面、登录媒体或无法访问来源如实提示未分析，可上传文件。UNKNOWN/失败记录不自动下载重试；本轮仅用离线下载fixture验证，真实外网源未验收。

Director接受独立检查：准确style_confirmed版本、实际Plan.director_revision_id、可见output与文件hash；完整QC passed或受限manual_review_only资格。人工资格还须技术pass、语义not_tested且无任何semantic fail/partial、成功Run和reviewable Work、明确manual_review_confirmed；只写director_accepted回执，不把QC改为PASS，也不依赖作品已经接受。设频道默认依赖该Director实际接受，必须关联并保留其他关系。

删除聊天撤销工具继续能力；正文/附件/回答副本清理，保留最少在途turn/命令映射直到核实。Work、必要brief、目录和媒体独立存续。原生内部历史不会复制回新Work/Profile段；宿主撤销访问不等于已经物理清除Gateway磁盘上的原生转录，不以此宣称完整账户数据擦除。

### 9.10 A2～A4实际落地与部署边界

A2持久记录/来源/工具桥与频道语义、A3统一对话/程序卡/共享详情、A4审片/版本/独立接受/受控保存/续作均已实现。源码入口为[easel/conversation.py](../../easel/conversation.py)、[持久工具桥](../../easel/conversation_bridge.py)、[Web适配](../../web/conversation_api.py)、[共享作品详情](../../web/frontend/src/components/WorkCards.tsx)和[对话入口](../../web/frontend/src/components/VideoConversation.tsx)。

已执行的是具名软件回归、原生隔离HTTP/Web探针及部分实际浏览器操作，证据和限制见任务卡。**A5的28项离线矩阵及完整本地媒体闭环已通过；正式插件/权限合成配置、正式库迁移与服务加载、新一轮真实付费Web生产、Creator接受均未执行。** 不用实现状态替代这些运行结果；具体部署字段见运行说明，不在此保存真实凭证或个人配置。

### 9.11 A5验收后的合同补正

入口导航每次具名选择生成新的enter命令；服务端按同Work/依据复用原运行段。导航不创建Work/Run，避免永久复用旧导航回执导致当前段未切换。生产/保存命令仍按精确目标、版本和载荷持久去重。

创建前对话与Work创建共用merge_creation_settings，字幕按字段继承，音色与导演身份整体覆盖。Planning将固定voice/subtitles按同一Pydantic合同展开后比较，等价缺省值可通过，明确变更仍阻断。频道名称要求非空文字，非法提案保存失败时保留proposed且无catalog回执。

受限工作区装载经审查的Easel产线交互知识及来源SHA，保留“先让用户看见方案、预览和真实检查，再作明确决定”的经验；不加载旧可执行技能。原生memory-core组合实测仍只暴露8个作品工具；正式其他插件/自动记忆/slash入口合成权限仍待部署环境复核，不能推广为OS隔离。

界面显示具体导演名/版本、参考文件名和中文任务状态。已接受的当前作品版、已生效的频道默认显示完成并禁用重复提交；独立失败项仍可单独处理。普通聊天通过明确视频入口才进入作品模式，内容库只投影已接受版，不因有新预览换掉原选择。逐项运行证据见[S6-14A](tasks/S6-14A_conversation-integration.md)。
